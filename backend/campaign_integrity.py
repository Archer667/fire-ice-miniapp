"""Validate stored army records without deleting, rewriting or inventing units."""
from datetime import datetime
from math import isfinite

LABELS = {'tg_id':'مالک لشکر', 'player_name':'نام مالک', 'origin_castle':'مبدأ',
          'target_castle':'مقصد', 'op_type':'نوع مأموریت', 'troops':'ترکیب نیروها',
          'created_at':'زمان ثبت', 'gold_cost':'هزینهٔ طلا', 'men_committed':'نفرات اعزامی',
          'equipment':'ادوات', 'arrival_at':'زمان رسیدن'}


def numeric(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value) and value>=0


def movement_issues(row):
    issues=[]
    if not isinstance(row.get('tg_id'),int) or isinstance(row.get('tg_id'),bool):issues.append('tg_id')
    for key in ('player_name','origin_castle','target_castle','op_type'):
        if not isinstance(row.get(key),str) or not row[key].strip():issues.append(key)
    troops=row.get('troops')
    if not isinstance(troops,dict) or any(not numeric(n) or int(n)!=n for n in troops.values()):issues.append('troops')
    equipment=row.get('equipment',{})
    if not isinstance(equipment,dict) or any(not numeric(n) or int(n)!=n for n in equipment.values()):issues.append('equipment')
    if row.get('arrival_at') is not None and not isinstance(row['arrival_at'],datetime):issues.append('arrival_at')
    return issues


def display_issues(row):
    issues=movement_issues(row)
    if not isinstance(row.get('created_at'),datetime):issues.append('created_at')
    for key in ('gold_cost','men_committed'):
        if not numeric(row.get(key)):issues.append(key)
    return issues


def issue_view(row,issues):
    return {'id':str(row['_id']), 'data_issues':issues, 'data_issue_labels':[LABELS.get(k,k) for k in issues],
            'player':row.get('player_name') or 'مالک ثبت نشده', 'name':row.get('name') or 'لشکر بدون نام',
            'from':row.get('origin_castle'), 'to':row.get('target_castle'),
            'merge_group_id':str(row.get('merge_group_id') or ''), 'active':bool(row.get('active'))}
