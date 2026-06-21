{% macro canonical_team(col) -%}
-- Normalize an nflverse team abbreviation to the franchise-canonical form so the
-- weekly-stats convention (LV/LA always) and the schedule convention (OAK for
-- 2018-19, plus assorted legacy spellings) join on the same key.
case {{ col }}
    when 'OAK' then 'LV'
    when 'SD'  then 'LAC'
    when 'STL' then 'LA'
    when 'LAR' then 'LA'
    when 'SL'  then 'LA'
    when 'WSH' then 'WAS'
    when 'ARZ' then 'ARI'
    when 'BLT' then 'BAL'
    when 'CLV' then 'CLE'
    when 'HST' then 'HOU'
    when 'JAC' then 'JAX'
    else {{ col }}
end
{%- endmacro %}
