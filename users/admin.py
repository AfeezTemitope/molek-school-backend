from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, ClassCounter, Student, TeacherAssignment


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'role', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'created_at']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['-created_at']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Custom Fields', {'fields': ('role',)}),
    )
    # Make password field read-only to prevent direct editing
    readonly_fields = ['password']

    def save_model(self, request, obj, form, change):
        # If creating a new user and a plain text password is provided, hash it
        if not change and 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


@admin.register(ClassCounter)
class ClassCounterAdmin(admin.ModelAdmin):
    list_display = ['class_name', 'count']
    readonly_fields = ['count']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        'admission_number',
        'first_name',
        'last_name',
        'get_full_class',
        'parent_phone',
        'created_by'
    ]
    readonly_fields = [
        'admission_number',
        'created_at',
        'updated_at',
        'user'
    ]
    search_fields = ['first_name', 'last_name', 'admission_number']
    list_filter = ['class_level', 'stream', 'section', 'created_by', 'created_at']

    fieldsets = (
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'gender', 'age', 'address')
        }),
        ('Class Info', {
            'fields': ('class_level', 'stream', 'section')
        }),
        ('Parent Info', {
            'fields': ('parent_phone', 'parent_email')
        }),
        ('Media', {
            'fields': ('passport_url',)
        }),
        ('System Info', {
            'fields': (
                'admission_number',
                'created_by',
                'created_at',
                'updated_at',
                'is_active'
            ),
            'classes': ('collapse',)
        }),
    )

    def get_full_class(self, obj):
        stream_part = f" {obj.stream}" if obj.stream else ""
        section_part = f" {obj.section}" if obj.section else ""
        return f"{obj.class_level}{stream_part}{section_part}"

    get_full_class.short_description = "Class"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            return qs.filter(created_by=request.user)
        return qs

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'level', 'stream', 'section', 'session_year']
    list_filter = ['level', 'stream', 'section', 'session_year', 'teacher']
    search_fields = ['teacher__username', 'teacher__first_name', 'teacher__last_name']
    autocomplete_fields = ['teacher']