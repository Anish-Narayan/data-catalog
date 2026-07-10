# PROVIDERS (Bright Care)

## Purpose
Contains comprehensive information about healthcare providers affiliated with Bright Care, including their specialties and contact details.

## Fields

| Field          | Meaning                                | Data Type   | Example          |
|----------------|----------------------------------------|-------------|------------------|
| PROVIDER_ID    | Unique provider identifier             | VARCHAR(50) | 'PROV-XYZ005'    |
| FIRST_NAME     | Provider's first name                  | VARCHAR(100)| 'Dr. Emily'      |
| LAST_NAME      | Provider's last name                   | VARCHAR(100)| 'Chen'           |
| SPECIALTY      | Provider's medical specialty           | VARCHAR(100)| 'Cardiology'     |
| NPI            | National Provider Identifier           | VARCHAR(10) | '1234567890'     |
| PRACTICE_NAME  | Name of the practice/clinic            | VARCHAR(255)| 'Heart Care Clinic' |
| CITY           | City where the practice is located     | VARCHAR(100)| 'Springfield'    |
| STATE          | State where the practice is located    | VARCHAR(2)  | 'IL'             |

## Related Tables

-   [PATIENT_VISITS](clients/bright_care_patient_visits.md) (One-to-many: One PROVIDERS to many PATIENT_VISITS via PROVIDER_ID)

## Sample Data

```sql
SELECT
    PROVIDER_ID,
    FIRST_NAME,
    LAST_NAME,
    SPECIALTY,
    NPI
FROM
    BRIGHTCARE.PROVIDERS
WHERE
    STATE = 'IL'
LIMIT 5;



