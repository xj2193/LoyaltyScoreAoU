SELECT DISTINCT person_id, omop_ext.src_id, omop.{{omop_table_id}} AS omop_table_id
FROM `{{omop_namespace}}.{{omop_table}}` omop
JOIN `{{output_namespace}}.mv_loyalty_score_concepts_with_standard_concepts` ls
ON omop.{{concept_column_name}} = ls.STANDARD_CONCEPT OR omop.{{source_concept_column_name}} = ls.NON_STANDARD_CONCEPT
JOIN `{{omop_namespace}}.{{omop_table}}_ext` omop_ext
ON (omop.{{omop_table_id}} = omop_ext.{{omop_table_id}})
WHERE {{date_column}} BETWEEN "{{start_date}}" AND "{{end_date}}"
AND ls.FEATURE_NAME = "{{feature_name}}"
AND ls.DOMAIN_ID = "{{domain_id}}"
AND omop_ext.src_id LIKE '%EHR site%'
