from django.urls import path, include
from rest_framework.routers import DefaultRouter

from base.auth.api_views import CustomObtainAuthToken
from base.auth.views import APILogoutView, CustomLoginView, LogoutView, ProfileView, UserRegistrationView
from base.dependencies.views import TaskDependencyViewSet
from base.projects.views import ProjectViewSet
from base.scheduling.views import global_schedule
from base.tasks.views import TaskViewSet
from base.users.views import UserViewSet



# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'tasks', TaskViewSet)
router.register(r'dependencies', TaskDependencyViewSet, basename='dependency')  




urlpatterns = [

    # API endpoints
    path('api/', include(router.urls)),
    path('api/schedule/', global_schedule, name='global-schedule'),
    path('api/logout/', APILogoutView.as_view(), name='api-logout'),
    path('api/register/', UserRegistrationView.as_view(), name='register'),

    # Auth endpoints
    path('api/auth-token/', CustomObtainAuthToken.as_view(), name='api_token_auth'),
    
    # Web views
    path('accounts/', include('django.contrib.auth.urls')),   #Was for debugging when I used django browsable api
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),


    path('accounts/profile/', ProfileView.as_view(), name='profile'),
]
