# PATIENT_VISITS (Bright Care)

## Purpose
Records each patient visit or encounter at a Bright Care facility, detailing the nature of the visit and key outcomes.

## Fields

| Field           | Meaning                                    | Data Type    | Example          |
|-----------------|--------------------------------------------|--------------|------------------|
| VISIT_ID        | Unique identifier for the patient visit    | VARCHAR(50)  | 'BRTC-V005001'   |
| PATIENT_ID      | Unique patient identifier                  | VARCHAR(50)  | 'PAT-112233'     |
| PROVIDER_ID     | ID of the primary provider for the visit   | VARCHAR(50)  | 'PROV-XYZ005'    |
| VISIT_DATE      | Date of the patient visit                  | DATE         | '2023-03-10'     |
| VISIT_TYPE      | Type of visit (e.g., Office, ER, Telehealth) | VARCHAR(50)  | 'Office Visit'   |
| DIAGNOSIS_CODE  | Primary diagnosis code (ICD-10)            | VARCHAR(10)  | 'I10'            |
| REASON_FOR_VISIT| Short description of visit reason          | VARCHAR(255) | 'Annual physical'|
| CHARGES_AMOUNT  | Total charges for the visit                | DECIMAL(18,2)| 250.00           |

## Related Tables

-   [PROVIDERS](clients/bright_care_providers.md) (Many-to-one: Many PATIENT_VISITS to one PROVIDERS via PROVIDER_ID)

## Sample Data

```sql
SELECT
    VISIT_ID,
    PATIENT_ID,
    VISIT_DATE,
    VISIT_TYPE,
    DIAGNOSIS_CODE
FROM
    BRIGHTCARE.PATIENT_VISITS
WHERE
    VISIT_DATE BETWEEN '2023-01-01' AND '2023-03-31'
LIMIT 5;