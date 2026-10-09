"""
Medical Q&A Retrieval Engine using TF-IDF and Cosine Similarity.
Retrieves relevant medical information from the clean MedQuAD dataset.
Includes low-confidence rejection, source attribution, and medical safety disclaimers.
"""

import json
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MEDICAL_DISCLAIMER = (
    "Disclaimer: This response is retrieved from verified public health resources "
    "(such as NIH and CDC) for general educational purposes only. It does not constitute "
    "medical advice, formal diagnosis, or treatment recommendation. Always consult a "
    "qualified healthcare provider for clinical evaluation."
)

FALLBACK_MESSAGE = (
    "I could not find a sufficiently confident answer in the verified medical dataset "
    "for your question. To ensure safety, answers are not generated when a reliable match "
    "is unavailable. Please rephrase your question or consult a qualified healthcare professional."
)


class MedicalRetrievalEngine:
    def __init__(self, data_path="data/medquad_clean.json"):
        self.data_path = data_path
        self.records = []
        self.questions = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _load_and_index(self):
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Clean dataset not found at '{self.data_path}'. Please run prepare_data.py first.")

        with open(self.data_path, "r", encoding="utf-8") as f:
            self.records = json.load(f)

        if not self.records:
            raise ValueError(f"No records found in '{self.data_path}'.")

        self.questions = [r["question"] for r in self.records]

        # TF-IDF with unigrams + bigrams and sublinear scaling
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
            strip_accents="unicode"
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.questions)

    def _sanitize_query(self, query: str) -> str:
        if not query or not isinstance(query, str):
            return ""
        # Strip extraneous whitespace
        cleaned = query.strip()
        # If contains only punctuation or digits
        if not re.search(r"[a-zA-Z]", cleaned):
            return ""
        return cleaned

    def search(self, query: str, top_k: int = 1, threshold: float = 0.25):
        """
        Search the medical QA dataset for the most relevant answer.
        Returns a structured dictionary with match status, source attribution, and safety disclaimer.
        """
        sanitized = self._sanitize_query(query)
        
        # Empty or non-alphabetic query handling
        if not sanitized:
            return {
                "query": query,
                "is_matched": False,
                "score": 0.0,
                "threshold": threshold,
                "answer": "Please enter a valid medical question.",
                "matched_question": None,
                "source": None,
                "focus": None,
                "qtype": None,
                "url": None,
                "disclaimer": MEDICAL_DISCLAIMER
            }

        # Vectorize query
        query_vec = self.vectorizer.transform([sanitized])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Find best match
        best_idx = similarities.argmax()
        best_score = float(similarities[best_idx])

        # Low-confidence rejection check
        if best_score < threshold:
            return {
                "query": query,
                "is_matched": False,
                "score": round(best_score, 4),
                "threshold": threshold,
                "answer": FALLBACK_MESSAGE,
                "matched_question": self.records[best_idx]["question"],
                "source": None,
                "focus": None,
                "qtype": None,
                "url": None,
                "disclaimer": MEDICAL_DISCLAIMER
            }

        matched_record = self.records[best_idx]
        return {
            "query": query,
            "is_matched": True,
            "score": round(best_score, 4),
            "threshold": threshold,
            "answer": matched_record["answer"],
            "matched_question": matched_record["question"],
            "source": matched_record["source"],
            "focus": matched_record["focus"],
            "qtype": matched_record["qtype"],
            "url": matched_record["url"],
            "disclaimer": MEDICAL_DISCLAIMER
        }

    def search_top_k(self, query: str, top_k: int = 3, threshold: float = 0.25):
        """
        Retrieve up to top_k candidate matches for detailed evaluation and inspection.
        """
        sanitized = self._sanitize_query(query)
        if not sanitized:
            return []

        query_vec = self.vectorizer.transform([sanitized])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Sort indices descending
        top_indices = similarities.argsort()[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            rec = self.records[idx]
            results.append({
                "score": round(score, 4),
                "is_above_threshold": score >= threshold,
                "matched_question": rec["question"],
                "answer": rec["answer"],
                "source": rec["source"],
                "focus": rec["focus"],
                "qtype": rec["qtype"],
                "url": rec["url"]
            })
        return results


if __name__ == "__main__":
    engine = MedicalRetrievalEngine()
    test_query = "What are the symptoms of adult acute lymphoblastic leukemia?"
    res = engine.search(test_query, threshold=0.25)
    print("\n--- Test Query ---")
    print("Query:", res["query"])
    print("Matched:", res["is_matched"])
    print("Score:", res["score"])
    print("Matched Question:", res["matched_question"])
    print("Source:", res["source"])
    print("Focus:", res["focus"])
    print("URL:", res["url"])
    print("Answer snippet:", res["answer"][:150], "...")

