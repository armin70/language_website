from django import forms

from .models import ContactMessage


class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage

        fields = [
            "name",
            "email",
            "subject",
            "message",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "common-input mb-20 form-control",
                    "placeholder": "نام و نام خانوادگی",
                    "autocomplete": "name",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "common-input mb-20 form-control",
                    "placeholder": "آدرس ایمیل",
                    "autocomplete": "email",
                    "dir": "ltr",
                }
            ),

            "subject": forms.TextInput(
                attrs={
                    "class": "common-input mb-20 form-control",
                    "placeholder": "موضوع پیام",
                }
            ),

            "message": forms.Textarea(
                attrs={
                    "class": "common-textarea form-control",
                    "placeholder": "متن پیام خود را بنویسید",
                    "rows": 7,
                }
            ),
        }

        labels = {
            "name": "",
            "email": "",
            "subject": "",
            "message": "",
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        if len(name) < 2:
            raise forms.ValidationError(
                "لطفاً نام خود را به‌درستی وارد کنید."
            )

        return name

    def clean_subject(self):
        subject = self.cleaned_data["subject"].strip()

        if len(subject) < 3:
            raise forms.ValidationError(
                "موضوع پیام باید حداقل ۳ کاراکتر باشد."
            )

        return subject

    def clean_message(self):
        message = self.cleaned_data["message"].strip()

        if len(message) < 10:
            raise forms.ValidationError(
                "متن پیام باید حداقل ۱۰ کاراکتر باشد."
            )

        return message
