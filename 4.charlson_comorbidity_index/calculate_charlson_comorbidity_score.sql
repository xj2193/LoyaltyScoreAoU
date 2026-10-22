WITH charlson_data AS (
  SELECT person_id,
         "{{year_gap}}years" as lookback_year,
         SUM(weight) AS score
  FROM (
    SELECT DISTINCT cs.diag_category_id,
                    cs.weight,
                    cohort.person_id,
    FROM `{{UNIONED_EHR_NAMESPACE}}.unioned_ehr_person` AS cohort
    INNER JOIN `{{UNIONED_EHR_NAMESPACE}}.unioned_ehr_condition_occurrence` AS condition
        ON cohort.person_id = condition.person_id
    INNER JOIN `{{OUTPUT_NAMESPACE}}.charlson_concepts` AS cc
        ON condition.condition_concept_id = cc.concept_id
    INNER JOIN `{{OUTPUT_NAMESPACE}}.charlson_scoring` AS cs
        ON cc.diag_category_id = cs.diag_category_id
    WHERE condition.condition_start_date between "{{start_date}}" and "{{end_date}}"
  )
  GROUP BY person_id
)

-- Step 2: Select the Charlson scores for each person
SELECT person_id,
       lookback_year,
       score
FROM charlson_data
ORDER BY person_id