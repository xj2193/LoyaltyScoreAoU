SELECT DISTINCT person_id, omop_ext.src_id, omop.{{omop_table_id}} AS omop_table_id
FROM `{{omop_namespace}}.{{omop_table}}` omop
JOIN `{{omop_namespace}}.{{omop_table}}_ext` omop_ext
ON omop.{{omop_table_id}} = omop_ext.{{omop_table_id}}
JOIN `{{output_namespace}}.mv_loyalty_score_concepts_with_standard_concepts` ls
ON (omop.{{concept_column_name}} = ls.STANDARD_CONCEPT OR omop.{{source_concept_column_name}} = ls.NON_STANDARD_CONCEPT)
WHERE {{date_column}} BETWEEN "{{start_date}}" AND "{{end_date}}"
AND ls.FEATURE_NAME = "{{feature_name}}"
AND ls.DOMAIN_ID = "{{domain_id}}"
AND ls.STANDARD_CONCEPT != 4203722
AND ls.NON_STANDARD_CONCEPT != 4203722
AND omop_ext.src_id LIKE '%EHR site%'

UNION DISTINCT
SELECT DISTINCT person_id, omop_ext.src_id, omop.{{omop_table_id}} AS omop_table_id
FROM `{{omop_namespace}}.{{omop_table}}` omop
JOIN `{{omop_namespace}}.{{omop_table}}_ext` omop_ext
ON omop.{{omop_table_id}} = omop_ext.{{omop_table_id}}
JOIN `{{output_namespace}}.mv_loyalty_score_concepts_with_standard_concepts` ls
ON (omop.{{concept_column_name}} = ls.STANDARD_CONCEPT OR omop.{{source_concept_column_name}} = ls.NON_STANDARD_CONCEPT)
AND omop.value_as_concept_id = ls.value_as_concept_id
WHERE {{date_column}} BETWEEN "{{start_date}}" AND "{{end_date}}"
AND ls.FEATURE_NAME = "{{feature_name}}"
AND ls.DOMAIN_ID = "{{domain_id}}"
AND (ls.STANDARD_CONCEPT = 4203722
OR ls.NON_STANDARD_CONCEPT = 4203722)
AND omop_ext.src_id LIKE '%EHR site%'
