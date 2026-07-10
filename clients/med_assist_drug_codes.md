# DRUG_CODES (MedAssist)

## Purpose
A reference table containing information about National Drug Codes (NDC), including generic names, brand names, and drug classifications.

## Fields

| Field          | Meaning                                    | Data Type   | Example             |
|----------------|--------------------------------------------|-------------|---------------------|
| NDC_CODE       | National Drug Code (10 or 11 digits)       | VARCHAR(11) | '00002816901'       |
| GENERIC_NAME   | Generic name of the drug                   | VARCHAR(255)| 'Lisinopril'        |
| BRAND_NAME     | Brand name of the drug (if applicable)     | VARCHAR(255)| 'Zestril'           |
| DOSAGE_FORM    | Form of the drug (e.g., tablet, capsule)   | VARCHAR(100)| 'Tablet'            |
| STRENGTH       | Strength of the drug                       | VARCHAR(100)| '10mg'              |
| DRUG_CLASS     | Therapeutic drug class                     | VARCHAR(255)| 'ACE Inhibitor'     |
| STATUS         | Current status (e.g., Active, Inactive)    | VARCHAR(20) | 'Active'            |

## Related Tables

-   [PHARMACY_CLAIMS](clients/med_assist_pharmacy_claims.md) (One-to-many: One DRUG_CODES to many PHARMACY_CLAIMS via NDC_CODE)

## Sample Data

```sql
SELECT
    NDC_CODE,
    GENERIC_NAME,
    BRAND_NAME,
    DRUG_CLASS
FROM
    MEDASSIST.DRUG_CODES
WHERE
    DRUG_CLASS = 'ACE Inhibitor'
LIMIT 5;