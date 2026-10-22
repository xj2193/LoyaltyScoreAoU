WITH
  ehr_flag AS (
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'condition' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.condition_occurrence`
      JOIN `{{OMOP_NAMESPACE}}.condition_occurrence_ext`
      USING(condition_occurrence_id)
      WHERE src_id LIKE '%EHR site%'
  UNION ALL
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'drug' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.drug_exposure`
      JOIN `{{OMOP_NAMESPACE}}.drug_exposure_ext`
      USING(drug_exposure_id)
      WHERE src_id LIKE '%EHR site%'
  UNION ALL
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'measurement' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.measurement`
      JOIN `{{OMOP_NAMESPACE}}.measurement_ext`
      USING(measurement_id)
      WHERE src_id LIKE '%EHR site%'
  UNION ALL
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'procedure' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.procedure_occurrence`
      JOIN `{{OMOP_NAMESPACE}}.procedure_occurrence_ext`
      USING(procedure_occurrence_id)
      WHERE src_id LIKE '%EHR site%'
  UNION ALL
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'visit' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.visit_occurrence`
      JOIN `{{OMOP_NAMESPACE}}.visit_occurrence_ext`
      USING(visit_occurrence_id)
      WHERE src_id LIKE '%EHR site%'
  UNION ALL
    SELECT DISTINCT
      person_id,
      1 as ehr_flag,
      'observation' as omop_domain,
      src_id
      FROM `{{OMOP_NAMESPACE}}.observation`
      JOIN `{{OMOP_NAMESPACE}}.observation_ext`
      USING(observation_id)
      WHERE src_id LIKE '%EHR site%'
      AND observation_concept_id not in (4013886, 4135376, 4271761)
  ),
  ehr_exist AS (
  SELECT
    DISTINCT person_id,
    src_id,
    COUNT(DISTINCT omop_domain) as ehr_domain_count
  FROM
    ehr_flag
  GROUP BY person_id, src_id)

SELECT
  DISTINCT p.person_id AS patient_num_rid,
  rid.person_id AS patient_num_pid,
  c1.concept_name AS gender,
  c2.concept_name AS race,
  c3.concept_name AS ethnicity,
  c4.concept_name AS sex_at_birth,
  c5.concept_name AS self_reported_race_ethnicity,
  v1.src_id AS src_id,
  ROUND(DATE_DIFF(DATE('{{ANALYSIS_END_DATE}}'), DATE(p.birth_datetime), DAY)/365) AS age,
  DATE('{{ANALYSIS_END_DATE}}') AS INDEX_DT,
IF
  (ehr_exist.ehr_domain_count > 0, 1, 0) AS EHR_EXIST,
  MAX(v2.visit_start_date) AS LAST_VISIT
FROM
  `{{OMOP_NAMESPACE}}.person` p
JOIN `{{OMOP_NAMESPACE}}.person_ext` pe
  ON p.person_id = pe.person_id
JOIN `{{ID_CROSSWALK_TABLE}}` rid
  ON p.person_id = rid.research_id
JOIN (
  SELECT DISTINCT vc.person_id, ve.src_id
FROM
  `{{OMOP_NAMESPACE}}.visit_occurrence` vc
JOIN `{{OMOP_NAMESPACE}}.visit_occurrence_ext` ve
  ON vc.visit_occurrence_id = ve.visit_occurrence_id
) v1
ON p.person_id = v1.person_id
LEFT JOIN
  `{{OMOP_NAMESPACE}}.aou_death` d
  ON p.person_id = d.person_id
JOIN  `{{OMOP_NAMESPACE}}.concept` c1
  ON p.gender_concept_id = c1.concept_id
JOIN  `{{OMOP_NAMESPACE}}.concept` c2
  ON p.race_concept_id = c2.concept_id
JOIN  `{{OMOP_NAMESPACE}}.concept` c3
  ON p.ethnicity_concept_id = c3.concept_id
JOIN  `{{OMOP_NAMESPACE}}.concept` c4
  ON pe.sex_at_birth_concept_id = c4.concept_id
JOIN  `{{OMOP_NAMESPACE}}.concept` c5
  ON pe.self_reported_category_concept_id = c5.concept_id
LEFT JOIN
(SELECT vc.visit_occurrence_id, vc.visit_start_date, vc.person_id, ve.src_id
FROM
  `{{OMOP_NAMESPACE}}.visit_occurrence` vc
JOIN `{{OMOP_NAMESPACE}}.visit_occurrence_ext` ve
  ON vc.visit_occurrence_id = ve.visit_occurrence_id
WHERE ve.src_id LIKE '%EHR site%'
) v2
ON
  p.person_id = v2.person_id
AND v1.src_id = v2.src_id
-- check if there's any visit in the next year of prediction
AND v2.visit_start_date >= '{{ANALYSIS_END_DATE}}'
AND v2.visit_start_date <= DATE_ADD(DATE '{{ANALYSIS_END_DATE}}', INTERVAL 1 YEAR)
LEFT JOIN
  ehr_exist
ON
  p.person_id = ehr_exist.person_id
  AND v1.src_id = ehr_exist.src_id
-- exclude people who are dead
WHERE d.person_id IS NULL
AND v1.src_id LIKE '%EHR site%'
GROUP BY
  1,
  2,
  3,
  4,
  5,
  6,
  7,
  8,
  9,
  10,
  11
