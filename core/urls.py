from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('website.urls')),  # main page handled by courses app
    path('students/', include('students.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path("placement/", include("placement.urls")),
    path('toefl/', include('toefl.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)