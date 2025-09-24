from django.contrib import admin
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
    list_display = (
        'admission_number', 'first_name', 'last_name', 'class_name',
        'parent_phone', 'created_by', 'created_at', 'user'
    )
    list_filter = ('class_name', 'created_by', 'created_at')
    search_fields = ('admission_number', 'first_name', 'last_name', 'parent_phone')
    readonly_fields = ('admission_number', 'created_by', 'created_at', 'updated_at', 'user')
    fieldsets = (
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'gender', 'age', 'address', 'class_name')
        }),
        ('Parent Info', {
            'fields': ('parent_phone', 'parent_email')
        }),
        ('Media', {
            'fields': ('passport_url',)
        }),
        ('System Info', {
            'fields': ('admission_number', 'created_by', 'created_at', 'updated_at', 'is_active', 'user'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(created_by=request.user)
        return qs


@admin.register(ClassCounter)
class ClassCounterAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'count')
    readonly_fields = ('count',)