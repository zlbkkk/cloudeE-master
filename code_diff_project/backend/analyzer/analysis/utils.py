import json
from analyzer.models import AnalysisTask


def update_task_log(task_id, message):
    if not task_id: return
    try:
        task = AnalysisTask.objects.get(id=task_id)
        task.log_details = (task.log_details or "") + message + "\n"
        task.save()
    except:
        pass


def format_field(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)
