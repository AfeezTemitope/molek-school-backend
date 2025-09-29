from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from .models import UserProfile, Student, ClassCounter

admin.site.unregister(Group)

@admin.register(UserProfile)
class UserProfileAdmin(BaseUserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-created_at',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Fields', {'fields': ('role',)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(is_superuser=False)
        return qs

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['admission_number', 'first_name', 'last_name', 'class_name', 'parent_phone', 'created_by']
    readonly_fields = ['admission_number', 'created_at', 'updated_at']
    search_fields = ['first_name', 'last_name', 'admission_number']
    list_filter = ['class_name', 'created_by', 'created_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(created_by=request.user)
        return qs

    # ✅ NEW: Reset password to student's last name
    actions = ['reset_password_to_lastname']

    @admin.action(description="Reset password to student's last name")
    def reset_password_to_lastname(self, request, queryset):
        success_count = 0
        error_count = 0

        for student in queryset:
            try:
                user = student.user
                if not user:
                    continue

                # Set password to last name (e.g., Okafor)
                raw_password = student.last_name
                user.set_password(raw_password)
                user.save()

                # Log success
                self.log_change(request, student, f"Password reset to {raw_password} (last name)")
                success_count += 1
            except Exception as e:
                error_count += 1

        # Show message to admin
        if success_count > 0:
            self.message_user(
                request,
                f"Successfully reset passwords to last names for {success_count} students.",
                level=messages.SUCCESS
            )
        if error_count > 0:
            self.message_user(
                request,
                f"Failed to reset {error_count} students.",
                level=messages.ERROR
            )

    fieldsets = (
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'gender', 'age', 'address', 'class_name')
        }),
        ('Parent Info', {
            'fields': ('parent_phone', 'parent_email'),
        }),
        ('Media', {
            'fields': ('passport_url',)
        }),
        ('System Info', {
            'fields': ('admission_number', 'created_by', 'created_at', 'updated_at', 'is_active'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ClassCounter)
class ClassCounterAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'count')
    readonly_fields = ('count',)