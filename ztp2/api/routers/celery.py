from celery.result import AsyncResult
from fastapi import APIRouter, Depends

from ..schemas.celery import Task, TaskCreateRequest, TaskCreateResponse
from ..stub import celery_stub

celery_router = APIRouter()


@celery_router.post('/', response_model=TaskCreateResponse)
async def celery_start_task(req: TaskCreateRequest,
                            celery=Depends(celery_stub)):
    task = celery.send_task(req.name, args=req.args, kwargs=req.kwargs)
    response = TaskCreateResponse(task_id=task.task_id)
    return response


@celery_router.get('/', response_model=list[Task])
async def celery_list(celery=Depends(celery_stub)):
    inspect = celery.control.inspect()
    workers_tasks = inspect.active()
    active_tasks = []
    for task_list in workers_tasks.values():
        for task_dict in task_list:
            task = AsyncResult(id=task_dict['id'], app=celery)
            active_tasks.append(Task(task_id=task.task_id, name=task.name,
                                     status=task.status, args=task.args,
                                     kwargs=task.kwargs, info=task.info))
    return active_tasks


@celery_router.get('/{celery_id}/', response_model=Task | None)
async def celery_get_task_info(celery_id: str,
                               celery=Depends(celery_stub)):
    task = AsyncResult(id=celery_id, app=celery)
    if task.task_id:
        response = Task(task_id=task.task_id, name=task.name,
                        status=task.status, args=task.args, kwargs=task.kwargs,
                        info=task.info)
    else:
        response = None
    return response


@celery_router.delete('/{celery_id}/', response_model=Task | None)
async def celery_revoke_task(celery_id: str,
                             celery=Depends(celery_stub)):
    task = AsyncResult(id=celery_id, app=celery)
    if task.task_id:
        response = Task(task_id=task.task_id, name=task.name,
                        status=task.status, args=task.args, kwargs=task.kwargs,
                        info=task.info)
    else:
        response = None
    task.revoke(terminate=True)
    return response
