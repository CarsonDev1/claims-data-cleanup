COLUMNS = ["claim_id", "policy_id", "member_name", "claim_type", "diagnosis",
           "submitted_amount", "currency", "submitted_date", "status"]
CLAIM_TYPES = ["OUTPATIENT", "INPATIENT", "DENTAL", "MATERNITY"]
STATUSES = ["APPROVED", "REJECTED", "PENDING", "IN_REVIEW"]
# lowercased-key maps so lookups are case-insensitive
CLAIM_TYPE_MAP = {"outpatient": "OUTPATIENT", "outpateint": "OUTPATIENT", "op": "OUTPATIENT",
                  "inpatient": "INPATIENT", "ip": "INPATIENT",
                  "dental": "DENTAL", "maternity": "MATERNITY"}
CURRENCY_MAP = {"thb": "THB", "baht": "THB", "vnd": "VND"}
DIAGNOSES = ["Flu", "Dengue fever", "Hypertension", "Type 2 diabetes", "Bronchitis",
             "Appendicitis", "Migraine", "Gastritis", "Fracture", "Pneumonia",
             "Asthma", "Dental caries", "Pregnancy", "Conjunctivitis", "Lower back pain"]
ISSUE_TYPES = ["missing_claim_id", "duplicate_claim_id", "missing_policy_id", "name_casing",
               "claim_type_typo", "missing_diagnosis", "invalid_amount", "amount_comma_format",
               "currency_variant", "date_format_variant", "invalid_date",
               "status_out_of_enum", "exact_duplicate_row"]
