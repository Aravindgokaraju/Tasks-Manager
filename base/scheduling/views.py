from rest_framework.decorators import api_view
from rest_framework.response import Response
from base.services.scheduling import GlobalParallelScheduler


@api_view(['GET'])
def global_schedule(request):
    """Generate schedule for all projects"""
    scheduler = GlobalParallelScheduler()
    try:
        schedule = scheduler.generate_schedule()
        return Response(schedule)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)