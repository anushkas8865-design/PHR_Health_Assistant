"""
Prepare Clean MedQuAD Data for Retrieval
Parses both uppercase and lowercase XML schemas across all MedQuAD subfolders.
Filters out empty/stripped answers and extracts clean QA pairs with full metadata.
"""

import os
import glob
import json
import xml.etree.ElementTree as ET
from collections import Counter


def parse_medquad(data_dir="data/MedQuAD", output_file="data/medquad_clean.json"):
    print(f"Scanning XML files in '{data_dir}'...")
    xml_files = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.endswith(".xml"):
                xml_files.append(os.path.join(root, f))

    print(f"Found {len(xml_files)} XML files.")

    total_pairs_parsed = 0
    empty_answers_count = 0
    records = []
    
    missing_metadata = {
        "missing_source": 0,
        "missing_focus": 0,
        "missing_qtype": 0,
        "missing_url": 0
    }

    for file_path in xml_files:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Schema detection (Standard uppercase vs lowercase)
            is_lowercase = root.tag.lower() == "doc"

            if is_lowercase:
                # Lowercase schema (e.g., select NINDS files)
                doc_source = root.attrib.get("corpus") or root.attrib.get("source") or "NINDS"
                doc_url = root.attrib.get("url", "").strip()
                focus_elem = root.find("doctitle-focus")
                doc_focus = focus_elem.text.strip() if (focus_elem is not None and focus_elem.text) else ""

                pairs = root.findall(".//pair")
                for p in pairs:
                    total_pairs_parsed += 1
                    q_elem = p.find("question")
                    a_elem = p.find("answer")
                    
                    q_text = q_elem.text.strip() if (q_elem is not None and q_elem.text) else ""
                    a_text = a_elem.text.strip() if (a_elem is not None and a_elem.text) else ""
                    q_type = q_elem.attrib.get("qtype", "").strip() if q_elem is not None else ""

                    if not a_text or not q_text:
                        empty_answers_count += 1
                        continue

                    if not doc_source:
                        missing_metadata["missing_source"] += 1
                    if not doc_focus:
                        missing_metadata["missing_focus"] += 1
                    if not q_type:
                        missing_metadata["missing_qtype"] += 1
                    if not doc_url:
                        missing_metadata["missing_url"] += 1

                    records.append({
                        "id": f"{root.attrib.get('docid', 'unk')}_{p.attrib.get('pid', '1')}",
                        "question": q_text,
                        "answer": a_text,
                        "source": doc_source,
                        "focus": doc_focus,
                        "qtype": q_type,
                        "url": doc_url
                    })
            else:
                # Standard uppercase schema
                doc_source = root.attrib.get("source", "").strip()
                doc_url = root.attrib.get("url", "").strip()
                focus_elem = root.find("Focus")
                doc_focus = focus_elem.text.strip() if (focus_elem is not None and focus_elem.text) else ""

                pairs = root.findall(".//QAPair")
                for p in pairs:
                    total_pairs_parsed += 1
                    q_elem = p.find("Question")
                    a_elem = p.find("Answer")

                    q_text = q_elem.text.strip() if (q_elem is not None and q_elem.text) else ""
                    a_text = a_elem.text.strip() if (a_elem is not None and a_elem.text) else ""
                    q_type = q_elem.attrib.get("qtype", "").strip() if q_elem is not None else ""

                    if not a_text or not q_text:
                        empty_answers_count += 1
                        continue

                    if not doc_source:
                        missing_metadata["missing_source"] += 1
                    if not doc_focus:
                        missing_metadata["missing_focus"] += 1
                    if not q_type:
                        missing_metadata["missing_qtype"] += 1
                    if not doc_url:
                        missing_metadata["missing_url"] += 1

                    records.append({
                        "id": f"{root.attrib.get('id', 'unk')}_{p.attrib.get('pid', '1')}",
                        "question": q_text,
                        "answer": a_text,
                        "source": doc_source,
                        "focus": doc_focus,
                        "qtype": q_type,
                        "url": doc_url
                    })

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

    # Check for duplicate questions
    question_counts = Counter([r["question"].lower() for r in records])
    duplicates_count = sum(count - 1 for count in question_counts.values() if count > 1)
    unique_questions = len(question_counts)

    print("\n=== EXTRACTION SUMMARY ===")
    print(f"Total XML files scanned: {len(xml_files)}")
    print(f"Total QA pairs parsed: {total_pairs_parsed}")
    print(f"Empty/unusable answers filtered: {empty_answers_count}")
    print(f"Usable QA pairs preserved: {len(records)}")
    print(f"Unique question texts: {unique_questions}")
    print(f"Duplicate question occurrences: {duplicates_count}")
    print(f"Metadata Completeness:")
    for k, v in missing_metadata.items():
        print(f"  - {k}: {v} (out of {len(records)})")

    # Save output to JSON
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"\nSuccessfully wrote clean dataset to '{output_file}' (Size: {os.path.getsize(output_file) / (1024*1024):.2f} MB)")
    return records


if __name__ == "__main__":
    parse_medquad()

