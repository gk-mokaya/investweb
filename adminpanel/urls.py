from django.urls import include, path

from compliance.urls import urlpatterns as compliance_urlpatterns
from dashboard.urls import urlpatterns as dashboard_urlpatterns
from finance.urls import urlpatterns as finance_urlpatterns
from users.urls import urlpatterns as users_urlpatterns


urlpatterns = dashboard_urlpatterns + users_urlpatterns + finance_urlpatterns + compliance_urlpatterns
