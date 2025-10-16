from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, Student

@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'created_at', 'updated_at')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'user', 'class_level', 'stream', 'section', 'is_active', 'created_at', 'updated_at')
    list_filter = ('class_level', 'stream', 'section', 'is_active')
    search_fields = ('admission_number', 'user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('admission_number', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('user', 'admission_number')}),
        ('Academic Info', {'fields': ('class_level', 'stream', 'section', 'passport')}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)