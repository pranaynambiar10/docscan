"""
DocScan Section Manager
Preserves complete document sections, page numbers, and hierarchical headings.
Supports both Mode A (RAG chunk retrieval) and Mode B (Full section retrieval).
"""

import os
import re
import sqlite3
import hashlib
from typing import List, Dict, Optional, Tuple

class SectionManager:
    def __init__(self, db_path: str = "documents.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS document_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                section_index INTEGER NOT NULL,
                section_title TEXT NOT NULL,
                parent_title TEXT DEFAULT '',
                page_start INTEGER DEFAULT 1,
                page_end INTEGER DEFAULT 1,
                start_offset INTEGER DEFAULT 0,
                end_offset INTEGER DEFAULT 0,
                content TEXT NOT NULL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sections_doc ON document_sections(document_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sections_id ON document_sections(document_id, section_id)')
        conn.commit()
        conn.close()

    # ── Section Extraction Logic ───────────────────────────────────────────────

    def parse_document_sections(self, filepath: str, filename: str) -> List[Dict]:
        """
        Parse a document into structured, page-aware sections.
        Detects:
          - Course headers (e.g. '23-202 -0701 - PRINCIPLES OF MANAGEMENT')
          - Module/Unit/Chapter headings ('Module I', 'Module II', 'Chapter 3')
          - Key document sections ('Course Outcomes', 'References', 'Terms & Conditions')
          - Subsections ('Inventory Management:', 'Financial Management:')
        Fallback: If no headings detected, breaks document into clean page-level sections.
        """
        import fitz

        sections = []
        ext = filename.lower().split('.')[-1]

        if ext == 'pdf':
            doc = fitz.open(filepath)
            pages = []
            for i in range(len(doc)):
                pages.append({'page_num': i + 1, 'text': doc[i].get_text()})
            doc.close()
            sections = self._parse_pages_into_sections(filename, pages)
        else:
            # Non-PDF or TXT/DOCX: extract text and parse text-based sections
            content = ""
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            sections = self._parse_text_into_sections(filename, content)

        # Fallback if no sections were produced
        if not sections and os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()
            sections = [{
                'document_id': filename,
                'section_id': 'sec_full',
                'section_index': 0,
                'section_title': 'Full Document',
                'parent_title': filename,
                'page_start': 1,
                'page_end': 1,
                'start_offset': 0,
                'end_offset': len(raw_text),
                'content': raw_text
            }]

        return sections

    def _parse_pages_into_sections(self, filename: str, pages: List[Dict]) -> List[Dict]:
        """Hierarchical parser for multi-page documents (academic syllabuses, manuals, etc.)"""
        sections = []
        current_course = ""
        current_course_page = 1

        # Patterns
        course_re = re.compile(r'(?m)^(?:\s*)(\d{2}-\d{3}\s*-\d{4}[A-Za-z*]?\s*[-–—]\s*[^\n]+)', re.IGNORECASE)
        module_re = re.compile(
            r'(?m)^(?:\s*)(MODULE\s+[IVXLCDM\d]+[^\n]*|UNIT\s+[IVXLCDM\d]+[^\n]*|CHAPTER\s+\d+[^\n]*|Course Outcomes:|References:)',
            re.IGNORECASE
        )

        global_char_offset = 0
        section_idx = 0

        # Buffer of text belonging to current module/section
        current_sec_title = "Course Introduction"
        current_sec_parent = ""
        current_sec_content = []
        current_sec_page_start = 1
        current_sec_page_end = 1
        current_sec_start_offset = 0

        def save_current_section():
            nonlocal section_idx, current_sec_content
            body = "".join(current_sec_content).strip()
            if body:
                safe_title = re.sub(r'[^a-zA-Z0-9]+', '_', current_sec_title).strip('_').lower()
                safe_parent = re.sub(r'[^a-zA-Z0-9]+', '_', current_sec_parent).strip('_').lower()[:30]
                sec_id = f"sec_{section_idx}_{safe_parent}_{safe_title}" if safe_parent else f"sec_{section_idx}_{safe_title}"

                sections.append({
                    'document_id': filename,
                    'section_id': sec_id[:60],
                    'section_index': section_idx,
                    'section_title': current_sec_title,
                    'parent_title': current_sec_parent or filename,
                    'page_start': current_sec_page_start,
                    'page_end': current_sec_page_end,
                    'start_offset': current_sec_start_offset,
                    'end_offset': current_sec_start_offset + len(body),
                    'content': body
                })
                section_idx += 1
            current_sec_content = []

        for p in pages:
            pnum = p['page_num']
            ptext = p['text']

            # Check if page introduces a new course/major subject
            cm = course_re.search(ptext)
            if cm:
                new_course = cm.group(1).strip()
                if new_course != current_course:
                    save_current_section()
                    current_course = new_course
                    current_sec_parent = new_course
                    current_course_page = pnum
                    current_sec_title = "Course Outcomes & Matrix"
                    current_sec_page_start = pnum
                    current_sec_page_end = pnum
                    current_sec_start_offset = global_char_offset + cm.start()

            # Check for Module or Major section boundaries on this page
            matches = list(module_re.finditer(ptext))
            if not matches:
                current_sec_content.append(ptext)
                current_sec_page_end = pnum
            else:
                last_idx = 0
                for m in matches:
                    before_text = ptext[last_idx:m.start()]
                    if before_text.strip():
                        current_sec_content.append(before_text)
                    save_current_section()

                    # Start new section
                    current_sec_title = m.group(1).strip().replace('\n', ' ')
                    current_sec_page_start = pnum
                    current_sec_page_end = pnum
                    current_sec_start_offset = global_char_offset + m.start()
                    current_sec_content = [m.group(0)]
                    last_idx = m.end()

                remainder = ptext[last_idx:]
                if remainder:
                    current_sec_content.append(remainder)

            global_char_offset += len(ptext)

        save_current_section()

        # Fallback if whole document produced only 1 big section
        if len(sections) <= 1 and len(pages) > 1:
            sections = []
            char_off = 0
            for idx, p in enumerate(pages):
                sections.append({
                    'document_id': filename,
                    'section_id': f"page_{p['page_num']}",
                    'section_index': idx,
                    'section_title': f"Page {p['page_num']}",
                    'parent_title': filename,
                    'page_start': p['page_num'],
                    'page_end': p['page_num'],
                    'start_offset': char_off,
                    'end_offset': char_off + len(p['text']),
                    'content': p['text'].strip()
                })
                char_off += len(p['text'])

        return sections

    def _parse_text_into_sections(self, filename: str, content: str) -> List[Dict]:
        """Parse raw text/DOCX documents into heading-based sections"""
        heading_re = re.compile(
            r'(?m)^(?:\s*)(?:(\d{1,2}\.\s+[^\n]+)|([A-Z\s]{4,40}:?)|(MODULE\s+[IVXLCDM\d]+[^\n]*)|(CHAPTER\s+\d+[^\n]*))'
        )
        matches = list(heading_re.finditer(content))
        if not matches:
            return [{
                'document_id': filename,
                'section_id': 'sec_full',
                'section_index': 0,
                'section_title': 'Full Document',
                'parent_title': filename,
                'page_start': 1,
                'page_end': 1,
                'start_offset': 0,
                'end_offset': len(content),
                'content': content
            }]

        sections = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            title = m.group(0).strip().rstrip(':')
            body = content[start:end].strip()
            safe_title = re.sub(r'[^a-zA-Z0-9]+', '_', title).strip('_').lower()[:30]

            sections.append({
                'document_id': filename,
                'section_id': f"sec_{i}_{safe_title}",
                'section_index': i,
                'section_title': title,
                'parent_title': filename,
                'page_start': 1,
                'page_end': 1,
                'start_offset': start,
                'end_offset': end,
                'content': body
            })
        return sections

    # ── Database Operations ───────────────────────────────────────────────────

    def save_sections(self, document_id: str, sections: List[Dict]):
        """Persist extracted sections in SQLite"""
        conn = self._get_conn()
        conn.execute('DELETE FROM document_sections WHERE document_id = ?', (document_id,))
        for s in sections:
            conn.execute('''
                INSERT INTO document_sections (
                    document_id, section_id, section_index, section_title,
                    parent_title, page_start, page_end, start_offset, end_offset, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                document_id,
                s['section_id'],
                s['section_index'],
                s['section_title'],
                s.get('parent_title', ''),
                s.get('page_start', 1),
                s.get('page_end', 1),
                s.get('start_offset', 0),
                s.get('end_offset', 0),
                s['content']
            ))
        conn.commit()
        conn.close()
        print(f"💾 Saved {len(sections)} structured sections for '{document_id}'")

    def get_sections(self, document_id: str) -> List[Dict]:
        """Fetch all section metadata for a document"""
        conn = self._get_conn()
        rows = conn.execute('''
            SELECT id, section_id, section_index, section_title, parent_title,
                   page_start, page_end, start_offset, end_offset, LENGTH(content) as content_length
            FROM document_sections
            WHERE document_id = ?
            ORDER BY section_index ASC
        ''', (document_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_section_by_id(self, document_id: str, section_id: str) -> Optional[Dict]:
        """Fetch full extracted content of a specific section"""
        conn = self._get_conn()
        row = conn.execute('''
            SELECT * FROM document_sections
            WHERE document_id = ? AND section_id = ?
            LIMIT 1
        ''', (document_id, section_id)).fetchone()
        conn.close()
        return dict(row) if row else None

    def find_section_for_chunk(self, document_id: str, chunk_text: str) -> Optional[Dict]:
        """Match a text chunk back to its corresponding structured section in SQLite"""
        conn = self._get_conn()
        sections = conn.execute(
            'SELECT * FROM document_sections WHERE document_id = ? ORDER BY section_index ASC',
            (document_id,)
        ).fetchall()
        conn.close()
        if not sections or not chunk_text:
            return None

        chunk_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', chunk_text.lower()))
        if not chunk_words:
            return None

        best_sec = None
        best_overlap = 0

        for s in sections:
            content_lower = s['content'].lower()
            if chunk_text[:40].lower() in content_lower:
                return dict(s)
            sec_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', content_lower))
            overlap = len(chunk_words.intersection(sec_words))
            if overlap > best_overlap:
                best_overlap = overlap
                best_sec = s

        if best_sec and best_overlap >= 3:
            return dict(best_sec)
        return None

    # ── Intelligent Query Classifier & Section Resolver ───────────────────────

    def resolve_query_section(self, document_id: str, question: str, context_hint: str = None) -> Dict:
        """
        Determine whether user wants:
          A. Complete Syllabus of a course ("Give me the full Principles of Management syllabus")
          B. Complete Module or Section ("Show me the complete Module II", "Show full section on inventory management")
          C. Specific RAG query ("What is included in Module I?", "What are the functions of inventory management?")
        """
        q_lower = question.lower()
        combined_context = f"{question} {context_hint or ''}".lower()

        conn = self._get_conn()
        all_sections = conn.execute(
            'SELECT * FROM document_sections WHERE document_id = ? ORDER BY section_index ASC',
            (document_id,)
        ).fetchall()
        conn.close()

        if not all_sections:
            return {'is_full_request': False, 'mode': 'rag'}

        sections = [dict(s) for s in all_sections]

        # ── 1. Check for Full Course / Syllabus Request ───────────────────────
        full_course_keywords = ['full syllabus', 'complete syllabus', 'entire syllabus', 'whole syllabus', 'all modules']
        is_full_syllabus = any(k in q_lower for k in full_course_keywords) or (
            ('syllabus' in q_lower or 'course' in q_lower) and ('full' in q_lower or 'all' in q_lower or 'complete' in q_lower)
        )

        if is_full_syllabus:
            best_course_name = self._find_best_course_name(sections, combined_context)
            if best_course_name:
                course_sections = [s for s in sections if s['parent_title'] == best_course_name]
            else:
                course_sections = sections

            # Sort sections by section_index to preserve exact curriculum order
            course_sections.sort(key=lambda x: x['section_index'])

            combined_text = []
            page_min = 999999
            page_max = 0

            for cs in course_sections:
                combined_text.append(f"### {cs['section_title']} (Page {cs['page_start']})\n\n{cs['content']}")
                page_min = min(page_min, cs['page_start'])
                page_max = max(page_max, cs['page_end'])

            return {
                'is_full_request': True,
                'mode': 'full_course',
                'section_title': f"Complete Syllabus: {best_course_name or 'Course Syllabus'}",
                'parent_title': best_course_name or document_id,
                'page_range': f"Pages {page_min}–{page_max}" if page_min != page_max else f"Page {page_min}",
                'full_text': "\n\n" + ("=" * 40) + "\n\n".join(combined_text),
                'matched_section_id': course_sections[0]['section_id'] if course_sections else ''
            }

        # ── 2. Check for Complete Module or Section Request ───────────────────
        full_sec_keywords = [
            'complete module', 'full module', 'entire module', 'whole module',
            'complete section', 'full section', 'entire section', 'whole section',
            'full text of', 'show me the complete', 'show the complete', 'show complete'
        ]
        is_full_section_req = any(k in q_lower for k in full_sec_keywords)

        # Detect module mention (e.g. "Module II", "Module 2", "Module I")
        module_roman_map = {
            '1': 'i', '2': 'ii', '3': 'iii', '4': 'iv', '5': 'v',
            'i': 'i', 'ii': 'ii', 'iii': 'iii', 'iv': 'iv', 'v': 'v'
        }
        mod_match = re.search(r'\bmodule\s+([ivx\d]+)\b', q_lower)
        target_mod_str = None
        if mod_match:
            raw_mod = mod_match.group(1).lower()
            target_mod_str = f"module {module_roman_map.get(raw_mod, raw_mod)}"

        if is_full_section_req and target_mod_str:
            # First find candidate modules matching target module string
            candidate_modules = [s for s in sections if target_mod_str in s['section_title'].lower()]
            
            # Prioritize candidate module whose parent_title has the highest word overlap with combined_context
            best_sec = None
            best_score = 0
            for s in candidate_modules:
                parent_lower = s['parent_title'].lower()
                parent_words = [w for w in re.split(r'[^a-zA-Z0-9]+', parent_lower) if len(w) > 3]
                score = sum(5 for w in parent_words if w in combined_context)
                if score > best_score:
                    best_score = score
                    best_sec = s

            if not best_sec and candidate_modules:
                # If no score was achieved, check if candidate has 'principles of management' specifically
                mgmt_cand = [s for s in candidate_modules if 'principles of management' in s['parent_title'].lower()]
                if not mgmt_cand:
                    mgmt_cand = [s for s in candidate_modules if 'management' in s['parent_title'].lower()]
                if mgmt_cand:
                    best_sec = mgmt_cand[0]
                else:
                    best_sec = candidate_modules[0]

            if best_sec:
                return {
                    'is_full_request': True,
                    'mode': 'full_section',
                    'section_title': best_sec['section_title'],
                    'parent_title': best_sec['parent_title'],
                    'page_range': f"Page {best_sec['page_start']}" if best_sec['page_start'] == best_sec['page_end'] else f"Pages {best_sec['page_start']}–{best_sec['page_end']}",
                    'full_text': best_sec['content'],
                    'matched_section_id': best_sec['section_id']
                }

        # Check for "entire section on <topic>" (e.g. "full section on inventory management")
        topic_match = re.search(r'(?:full|complete|entire|whole)\s+section\s+(?:on|about|for)\s+([a-zA-Z\s]{3,35})', q_lower)
        if topic_match:
            topic = topic_match.group(1).strip().lower()
            # Scan sections for this topic
            best_sec = None
            best_sub_content = None

            for s in sections:
                if topic in s['content'].lower():
                    sub = self._extract_subsection(s['content'], topic)
                    if sub:
                        best_sec = s
                        best_sub_content = sub
                        break
                    elif not best_sec:
                        best_sec = s
                        best_sub_content = s['content']

            if best_sec:
                return {
                    'is_full_request': True,
                    'mode': 'full_section',
                    'section_title': f"{best_sec['section_title']} - {topic.title()}",
                    'parent_title': best_sec['parent_title'],
                    'page_range': f"Page {best_sec['page_start']}",
                    'full_text': best_sub_content or best_sec['content'],
                    'matched_section_id': best_sec['section_id']
                }

        # Default: normal focused RAG query
        return {'is_full_request': False, 'mode': 'rag'}

    def _find_best_course_name(self, sections: List[Dict], query_text: str) -> str:
        """Find matching course title from text mentions"""
        unique_parents = list(dict.fromkeys([s['parent_title'] for s in sections if s['parent_title']]))
        
        # Check direct keyword matches
        for parent in unique_parents:
            parent_words = [w for w in re.split(r'[^a-zA-Z0-9]+', parent.lower()) if len(w) > 2]
            match_count = sum(1 for w in parent_words if w in query_text)
            if match_count >= 2:
                return parent

        # Check specific subject keywords
        if 'management' in query_text:
            for parent in unique_parents:
                if 'principles of management' in parent.lower() or ('principles' in parent.lower() and 'management' in parent.lower()):
                    return parent

        return unique_parents[0] if len(unique_parents) == 1 else ""

    def _extract_subsection(self, text: str, topic: str) -> Optional[str]:
        """Extract a distinct subsection paragraph matching topic (e.g. 'Inventory Management:') with scoring"""
        sub_re = re.compile(r'(?m)^(?:\s*)([A-Z][A-Za-z\s–—\-]{3,40}:)', re.IGNORECASE)
        matches = list(sub_re.finditer(text))
        if not matches:
            return None

        best_match = None
        best_score = 0
        topic_words = set([w for w in topic.split() if len(w) > 2])

        for i, m in enumerate(matches):
            title = m.group(1).rstrip(':').strip().lower()
            if topic == title or topic in title:
                score = 100
            else:
                score = sum(10 for w in topic_words if w in title)

            if score > best_score:
                best_score = score
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                best_match = text[start:end].strip()

        return best_match if best_score > 0 else None
