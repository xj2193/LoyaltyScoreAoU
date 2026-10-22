SELECT DISTINCT person_id, omop_ext.src_id, omop.{{omop_table_id}} AS omop_table_id
FROM `{{omop_namespace}}.{{omop_table}}` omop
JOIN `{{omop_namespace}}.{{omop_table}}_ext` omop_ext
ON omop.{{omop_table_id}} = omop_ext.{{omop_table_id}}
WHERE {{date_column}} BETWEEN "{{start_date}}" AND "{{end_date}}"
AND omop_ext.src_id LIKE '%EHR site%'