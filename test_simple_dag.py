#!/usr/bin/env python3

import sys
sys.path.append('/opt/airflow/dags')
sys.path.append('/app')

print('🌪️ Testing Simple DAG Loading...')
print('=' * 40)

try:
    from airflow.models import DagBag
    
    dag_bag = DagBag(dag_folder='/opt/airflow/dags', include_examples=False)
    
    # Check for import errors
    if dag_bag.import_errors:
        print('❌ DAG Import Errors:')
        for dag_file, error in dag_bag.import_errors.items():
            if 'broken' not in dag_file:  # Skip expected broken files
                print(f'   {dag_file}: {str(error)[:200]}...')
    else:
        print('✅ No DAG import errors')
    
    # Check available DAGs
    dag_ids = list(dag_bag.dag_ids)
    print(f'📊 Total DAGs loaded: {len(dag_ids)}')
    
    if 'simple_ticker_enrichment' in dag_ids:
        print('🎉 simple_ticker_enrichment DAG loaded successfully!')
        
        # Get DAG details
        simple_dag = dag_bag.get_dag('simple_ticker_enrichment')
        print(f'   📅 Schedule: {simple_dag.schedule_interval}')
        print(f'   📝 Tasks: {len(simple_dag.tasks)}')
        print(f'   📂 Task Groups: {len(simple_dag.task_group_dict)}')
        
        print('📋 Task Groups:')
        for tg_id in simple_dag.task_group_dict:
            tg = simple_dag.task_group_dict[tg_id]
            print(f'   - {tg_id} ({len(tg.children)} tasks)')
            
        print('📝 All Tasks:')
        for task in simple_dag.tasks:
            print(f'   - {task.task_id}')
            
    else:
        print('⚠️ simple_ticker_enrichment DAG not found')
        
    print(f'Available DAGs: {dag_ids}')
    print('✅ SIMPLE DAG LOADING TEST COMPLETE!')
    
except Exception as e:
    print(f'❌ Error testing DAG: {e}')
    import traceback
    traceback.print_exc()
