# POLICY_HOLDERS (Premier Insurers)

## Purpose
Stores demographic and contact information for each individual who holds an insurance policy with Premier Insurers.

## Fields

| Field          | Meaning                                | Data Type   | Example          |
|----------------|----------------------------------------|-------------|------------------|
| POLICY_HOLDER_ID| Unique policy holder identifier       | VARCHAR(50) | 'PRMI-PH00100'   |
| FIRST_NAME     | Policy holder's first name             | VARCHAR(100)| 'John'           |
| LAST_NAME      | Policy holder's last name              | VARCHAR(100)| 'Doe'            |
| DATE_OF_BIRTH  | Policy holder's date of birth          | DATE        | '1978-11-22'     |
| EMAIL          | Policy holder's email address          | VARCHAR(255)| 'john.doe@email.com'|
| PHONE_NUMBER   | Policy holder's phone number           | VARCHAR(20) | '555-123-4567'   |
| ADDRESS        | Policy holder's street address         | VARCHAR(255)| '123 Main St'    |
| CITY           | Policy holder's city                   | VARCHAR(100)| 'Anytown'        |
| STATE          | Policy holder's state                  | VARCHAR(2)  | 'CA'             |
| ZIP_CODE       | Policy holder's ZIP code               | VARCHAR(10) | '90210'          |

## Related Tables

-   [POLICIES](clients/premier_insurers_policies.md) (One-to-many: One POLICY_HOLDERS to many POLICIES via POLICY_HOLDER_ID)

## Sample Data

```sql
SELECT
    POLICY_HOLDER_ID,
    FIRST_NAME,
    LAST_NAME,
    EMAIL,
    STATE
FROM
    PREMIERINSURERS.POLICY_HOLDERS
WHERE
    STATE = 'CA'
LIMIT 5;