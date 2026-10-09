"""
Evaluation & Threshold Calibration Suite for MedQuAD NLP Retrieval Engine.
Evaluates retrieval performance across multiple candidate similarity thresholds
using a documented benchmark of medical, paraphrased, out-of-domain, and noisy queries.
"""

import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from retrieval.engine import MedicalRetrievalEngine


# Documented Evaluation Test Suite
EVALUATION_DATASET = [
    # Category 1: Direct / Close Medical Matches (Target: Accept with correct clinical focus)
    {
        "id": "DIR_01",
        "category": "Direct Medical",
        "query": "What are the symptoms of Adult Acute Lymphoblastic Leukemia ?",
        "expected_focus": "Adult Acute Lymphoblastic Leukemia",
        "should_accept": True
    },
    {
        "id": "DIR_02",
        "category": "Direct Medical",
        "query": "How is diabetes diagnosed ?",
        "expected_focus": "Diabetes",
        "should_accept": True
    },
    {
        "id": "DIR_03",
        "category": "Direct Medical",
        "query": "What causes Noonan syndrome ?",
        "expected_focus": "Noonan syndrome",
        "should_accept": True
    },
    {
        "id": "DIR_04",
        "category": "Direct Medical",
        "query": "What are the treatments for high blood pressure ?",
        "expected_focus": "High Blood Pressure",
        "should_accept": True
    },
    {
        "id": "DIR_05",
        "category": "Direct Medical",
        "query": "what is holmes-adie syndrome ?",
        "expected_focus": "Holmes-Adie",
        "should_accept": True
    },
    {
        "id": "DIR_06",
        "category": "Direct Medical",
        "query": "What are the risk factors for breast cancer ?",
        "expected_focus": "Breast Cancer",
        "should_accept": True
    },
    {
        "id": "DIR_07",
        "category": "Direct Medical",
        "query": "How to prevent stroke ?",
        "expected_focus": "Stroke",
        "should_accept": True
    },
    {
        "id": "DIR_08",
        "category": "Direct Medical",
        "query": "What are the symptoms of Parkinson's disease ?",
        "expected_focus": "Parkinson's Disease",
        "should_accept": True
    },
    {
        "id": "DIR_09",
        "category": "Direct Medical",
        "query": "What is sickle cell disease ?",
        "expected_focus": "Sickle Cell Disease",
        "should_accept": True
    },
    {
        "id": "DIR_10",
        "category": "Direct Medical",
        "query": "What is the outlook for Alzheimer's disease ?",
        "expected_focus": "Alzheimer's Disease",
        "should_accept": True
    },

    # Category 2: Paraphrased / Colloquial Medical Questions (Target: Accept with relevant clinical focus)
    {
        "id": "PAR_01",
        "category": "Paraphrased Medical",
        "query": "How do doctors tell if a patient has diabetes mellitus?",
        "expected_focus": "Diabetes",
        "should_accept": True
    },
    {
        "id": "PAR_02",
        "category": "Paraphrased Medical",
        "query": "What signs indicate that someone might have leukemia?",
        "expected_focus": "Leukemia",
        "should_accept": True
    },
    {
        "id": "PAR_03",
        "category": "Paraphrased Medical",
        "query": "Is there a cure or therapy available for Holmes-Adie disorder?",
        "expected_focus": "Holmes-Adie",
        "should_accept": True
    },
    {
        "id": "PAR_04",
        "category": "Paraphrased Medical",
        "query": "Why does a person develop Noonan syndrome?",
        "expected_focus": "Noonan syndrome",
        "should_accept": True
    },
    {
        "id": "PAR_05",
        "category": "Paraphrased Medical",
        "query": "Ways to reduce my chance of having a stroke",
        "expected_focus": "Stroke",
        "should_accept": True
    },
    {
        "id": "PAR_06",
        "category": "Paraphrased Medical",
        "query": "What medications or interventions lower high arterial blood pressure?",
        "expected_focus": "High Blood Pressure",
        "should_accept": True
    },
    {
        "id": "PAR_07",
        "category": "Paraphrased Medical",
        "query": "Early warning signs of Parkinson disease in older adults",
        "expected_focus": "Parkinson's Disease",
        "should_accept": True
    },
    {
        "id": "PAR_08",
        "category": "Paraphrased Medical",
        "query": "Inheritance and genetic causes of sickle cell anemia",
        "expected_focus": "Sickle Cell",
        "should_accept": True
    },

    # Category 3: Out-of-Domain / Non-Medical Queries (Target: REJECT safely)
    {
        "id": "OOD_01",
        "category": "Out-of-Domain",
        "query": "What is the capital city of France?",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_02",
        "category": "Out-of-Domain",
        "query": "How do I change a flat tire on my car?",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_03",
        "category": "Out-of-Domain",
        "query": "Who won the FIFA World Cup in 2022?",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_04",
        "category": "Out-of-Domain",
        "query": "Can you write Python code to sort a list?",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_05",
        "category": "Out-of-Domain",
        "query": "What is the weather forecast for tomorrow?",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_06",
        "category": "Out-of-Domain",
        "query": "Explain how quantum computers operate.",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_07",
        "category": "Out-of-Domain",
        "query": "Best recipe for baking chocolate chip cookies",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "OOD_08",
        "category": "Out-of-Domain",
        "query": "How do rockets escape Earth gravity?",
        "expected_focus": None,
        "should_accept": False
    },

    # Category 4: Noise / Empty / Invalid Queries (Target: REJECT safely)
    {
        "id": "NOISE_01",
        "category": "Noise/Invalid",
        "query": "",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "NOISE_02",
        "category": "Noise/Invalid",
        "query": "       ",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "NOISE_03",
        "category": "Noise/Invalid",
        "query": "?!?!??",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "NOISE_04",
        "category": "Noise/Invalid",
        "query": "12345 67890",
        "expected_focus": None,
        "should_accept": False
    },
    {
        "id": "NOISE_05",
        "category": "Noise/Invalid",
        "query": "asdfghjkl qwerty",
        "expected_focus": None,
        "should_accept": False
    }
]


def run_evaluation():
    print("Loading Medical Retrieval Engine...")
    t0 = time.time()
    engine = MedicalRetrievalEngine()
    print(f"Engine initialized with {len(engine.records)} records in {time.time() - t0:.2f}s.\n")

    thresholds_to_test = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    total_queries = len(EVALUATION_DATASET)
    medical_queries = [q for q in EVALUATION_DATASET if q["should_accept"]]
    non_medical_queries = [q for q in EVALUATION_DATASET if not q["should_accept"]]

    print(f"Total Test Suite Items: {total_queries}")
    print(f"  - Valid Medical Queries (Direct + Paraphrased): {len(medical_queries)}")
    print(f"  - Non-Medical / Noise Queries (OOD + Invalid): {len(non_medical_queries)}\n")

    results_table = []

    for thresh in thresholds_to_test:
        true_accepts = 0
        false_accepts = 0
        true_rejects = 0
        false_rejects = 0
        latencies = []

        for item in EVALUATION_DATASET:
            start_t = time.perf_counter()
            res = engine.search(item["query"], threshold=thresh)
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            latencies.append(elapsed_ms)

            is_accepted = res["is_matched"]

            if item["should_accept"]:
                if is_accepted:
                    # Normalize text (strip apostrophes) for clinical alignment check
                    matched_f = (res["focus"] or "").lower().replace("'s", "").replace("’s", "")
                    matched_q = (res["matched_question"] or "").lower().replace("'s", "").replace("’s", "")
                    exp_f = (item["expected_focus"] or "").lower().replace("'s", "").replace("’s", "")

                    if exp_f in matched_f or exp_f in matched_q:
                        true_accepts += 1
                    else:
                        # Accepted but matched incorrect disease
                        false_accepts += 1
                else:
                    false_rejects += 1
            else:
                # Expected rejection
                if is_accepted:
                    false_accepts += 1
                else:
                    true_rejects += 1

        acc = (true_accepts + true_rejects) / total_queries
        med_recall = true_accepts / len(medical_queries)
        rejection_rate = true_rejects / len(non_medical_queries)
        avg_latency = sum(latencies) / len(latencies)

        results_table.append({
            "threshold": thresh,
            "true_accepts": true_accepts,
            "false_accepts": false_accepts,
            "true_rejects": true_rejects,
            "false_rejects": false_rejects,
            "accuracy": acc,
            "med_recall": med_recall,
            "rejection_rate": rejection_rate,
            "avg_latency_ms": avg_latency
        })

    # Print Calibration Results Table
    print("=" * 105)
    print(f"{'Threshold':<10} | {'True Acc':<10} | {'False Acc':<10} | {'True Rej':<10} | {'False Rej':<10} | {'Accuracy':<10} | {'Med Recall':<12} | {'OOD Rejection':<14} | {'Latency':<10}")
    print("=" * 105)
    for r in results_table:
        print(f"{r['threshold']:<10.2f} | {r['true_accepts']:<10} | {r['false_accepts']:<10} | {r['true_rejects']:<10} | {r['false_rejects']:<10} | {r['accuracy']*100:<9.1f}% | {r['med_recall']*100:<11.1f}% | {r['rejection_rate']*100:<13.1f}% | {r['avg_latency_ms']:<8.2f}ms")
    print("=" * 105)

    # Detailed Inspection of Query Behaviors at Selected Threshold (0.25)
    print("\n\n=== DETAILED QUERY-BY-QUERY AUDIT AT THRESHOLD 0.25 ===")
    for item in EVALUATION_DATASET:
        res = engine.search(item["query"], threshold=0.25)
        status_flag = "PASS"
        if item["should_accept"] and not res["is_matched"]:
            status_flag = "FALSE_REJECT"
        elif not item["should_accept"] and res["is_matched"]:
            status_flag = "FALSE_ACCEPT"
        
        display_q = f"'{item['query']}'" if item['query'].strip() else "'' (Empty/Blank)"
        print(f"[{item['id']}] [{item['category']}] Query: {display_q}")
        print(f"      Matched: {res['is_matched']} | Score: {res['score']} | Status: {status_flag}")
        if res["is_matched"]:
            print(f"      Matched Condition: {res['focus']} (Source: {res['source']})")
            print(f"      Matched Question:  {res['matched_question']}")
        else:
            print(f"      Fallback Given:    {res['answer'][:70]}...")
        print()


if __name__ == "__main__":
    run_evaluation()
