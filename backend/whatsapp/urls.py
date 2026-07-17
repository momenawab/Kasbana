from django.urls import path

from .views import SendWhatsAppOTPView, VerifyWhatsAppOTPView, WhatsAppWebhookView

urlpatterns = [
    path("auth/send-whatsapp-otp/", SendWhatsAppOTPView.as_view()),
    path("auth/verify-whatsapp-otp/", VerifyWhatsAppOTPView.as_view()),
    path("webhooks/whatsapp/", WhatsAppWebhookView.as_view()),
]
