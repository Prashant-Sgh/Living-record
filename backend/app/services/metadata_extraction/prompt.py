"""Prompt for clinical metadata extraction."""

METADATA_EXTRACTION_PROMPT = """You are a clinical data extraction engine analyzing an unstructured medical report. Extract structured metadata and return ONLY valid JSON matching this schema:

{
  "patient_id": "string or empty",
  "patient_name": "string or empty",
  "report_date": "string or empty",
  "visit_type": "string or empty",
  "conditions": ["array of strings"],
  "medications": ["array of strings"],
  "laboratory_tests": ["array of strings"],
  "laboratory_values": ["array of strings"],
  "providers": ["array of strings"],
  "procedures": ["array of strings"],
  "symptoms": ["array of strings"],
  "diagnoses": ["array of strings"],
  "recommendations": ["array of strings"]
}

STRICT RULES:
1. Never hallucinate or invent values.
2. Return empty arrays [] instead of null if a field is missing.
3. Return empty strings "" for missing text fields.
4. Output ONLY valid JSON, no additional text or explanations.
5. Use values exactly as written in the report.
"""

# Backward compatibility alias
PROMPT = METADATA_EXTRACTION_PROMPT