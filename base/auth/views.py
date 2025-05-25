from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView
from django.contrib.auth import get_user_model
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import logout as django_logout
from rest_framework.permissions import AllowAny

User = get_user_model()

class CustomLoginView(LoginView):
    """Standard Django login view with custom template and page title."""

    template_name = 'login.html'
    extra_context = {'title': 'Login'}

class ProfileView(LoginRequiredMixin, DetailView):
    """Displays the profile page for the currently logged-in user."""
    model = User
    template_name = 'profile.html'
    context_object_name = 'profile_user'

    def get_object(self):
        return self.request.user


class LogoutView(View):
    """Handles user logout and redirects to the home page."""
    def get(self, request):
        auth_logout(request)
        return redirect('home')
    
class APILogoutView(APIView):
    """API endpoint for logging out users (handles both token and session auth)."""

    def post(self, request):
        # Delete the token (if using TokenAuthentication)
        if hasattr(request, 'auth'):
            request.auth.delete()  # Deletes the token
        
        # Clear session (if using SessionAuthentication)
        django_logout(request)
        
        # Return success response (no redirect)
        print("Success!!")
        return Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK
        )
    

class UserRegistrationView(APIView):
    """API endpoint for creating new user accounts (username/password required)."""
    permission_classes = [AllowAny]

    def post(self, request):
        # Validate required fields
        if 'username' not in request.data or 'password' not in request.data:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        username = request.data['username']
        email = request.data.get('email', '')  # Optional field

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username already exists'},
                status=status.HTTP_409_CONFLICT
            )

        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                password=request.data['password'],
                email=email  # Can be empty or duplicate
            )
            return Response(
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )