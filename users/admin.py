from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
import re

from .models import (
    UserProfile,
    AcademicSession,
    Term,
    ClassLevel,
    Subject,
    ActiveStudent,
    CAScore,
    ExamResult,
    PromotionRule,
)


# ==============================================================================
# USER PROFILE ADMIN
# ==============================================================================
class UserProfileAdminForm(forms.ModelForm):
    """Form for UserProfile in Django admin"""

    class Meta:
        model = UserProfile
        fields = '__all__'

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number and not re.match(r'^\+?1?\d{9,15}$', phone_number):
            raise forms.ValidationError('Invalid phone number format')
        return phone_number

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if role not in ['admin', 'superadmin']:
            raise forms.ValidationError('Role must be admin or superadmin')
        return role


@admin.register(UserProfile)
class UserProfileAdmin(UserAdmin):
    """Admin interface for UserProfile"""
    form = UserProfileAdminForm
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'is_active', 'is_staff', 'created_at'
    )
    list_filter = ('role', 'is_active', 'is_staff', 'sex')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': (
                'first_name', 'last_name', 'email', 'phone_number',
                'sex', 'age', 'address', 'state_of_origin', 'local_govt_area'
            )
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name', 'role',
                'phone_number', 'password1', 'password2'
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Auto-set is_staff for admins/superadmins"""
        if obj.role in ['admin', 'superadmin']:
            obj.is_staff = True
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Only show admin/superadmin users"""
        qs = super().get_queryset(request)
        return qs.filter(role__in=['admin', 'superadmin'])


# ==============================================================================
# ACADEMIC SESSION & TERM ADMIN
# ==============================================================================
@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current', 'created_at')
    list_filter = ('is_current',)
    search_fields = ('name',)
    ordering = ('-start_date',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('session', 'name', 'start_date', 'end_date', 'is_current')
    list_filter = ('session', 'name', 'is_current')
    search_fields = ('session__name', 'name')
    ordering = ('session', 'name')
    readonly_fields = ('created_at',)


# ==============================================================================
# CLASS LEVEL & SUBJECT ADMIN
# ==============================================================================
@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'description')
    ordering = ('order',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'class_levels')
    search_fields = ('name', 'code')
    filter_horizontal = ('class_levels',)
    ordering = ('name',)
    readonly_fields = ('created_at',)


# ==============================================================================
# ACTIVE STUDENT ADMIN
# ==============================================================================
@admin.register(ActiveStudent)
class ActiveStudentAdmin(admin.ModelAdmin):
    list_display = (
        'admission_number', 'full_name', 'gender', 'class_level',
        'is_active', 'created_at'
    )
    list_filter = ('class_level', 'gender', 'is_active', 'enrollment_session')
    search_fields = ('admission_number', 'first_name', 'last_name', 'email')
    filter_horizontal = ('subjects',)
    ordering = ('admission_number',)
    readonly_fields = ('admission_number', 'password_hash', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('admission_number', 'first_name', 'middle_name', 'last_name')
        }),
        ('Authentication', {
            'fields': ('password_plain', 'password_hash'),
            'classes': ('collapse',)
        }),
        ('Demographics', {
            'fields': ('date_of_birth', 'gender', 'state_of_origin', 'local_govt_area')
        }),
        ('Contact', {
            'fields': ('email', 'phone_number', 'address')
        }),
        ('Academic', {
            'fields': ('class_level', 'subjects', 'enrollment_session')
        }),
        ('Parent/Guardian', {
            'fields': ('parent_name', 'parent_email', 'parent_phone')
        }),
        ('Photo', {
            'fields': ('passport',)
        }),
        ('Status', {
            'fields': ('is_active', 'graduation_date')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ==============================================================================
# CA SCORE ADMIN (CA1 + CA2)
# ==============================================================================
@admin.register(CAScore)
class CAScoreAdmin(admin.ModelAdmin):
    """
    Admin for CA Scores (CA1 + CA2)
    Nigerian School Format: CA1 (15) + CA2 (15) = 30
    """
    list_display = (
        'get_admission_number', 'get_student_name', 'subject',
        'session', 'term',
        'ca1_score', 'ca2_score', 'get_total_ca',
        'updated_at'
    )
    list_filter = ('session', 'term', 'subject', 'student__class_level')
    search_fields = (
        'student__admission_number',
        'student__first_name',
        'student__last_name',
        'subject__name'
    )
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('student', 'subject')
    
    fieldsets = (
        ('Student & Subject', {
            'fields': ('student', 'subject', 'session', 'term')
        }),
        ('CA Scores (Max: CA1=15, CA2=15, Total=30)', {
            'fields': ('ca1_score', 'ca2_score'),
            'description': 'Enter Continuous Assessment scores. CA1 max is 15, CA2 max is 15.'
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Admission No.', ordering='student__admission_number')
    def get_admission_number(self, obj):
        return obj.student.admission_number

    @admin.display(description='Student Name')
    def get_student_name(self, obj):
        return obj.student.full_name

    @admin.display(description='Total CA')
    def get_total_ca(self, obj):
        return obj.total_ca_score


# ==============================================================================
# EXAM RESULT ADMIN (CA1 + CA2 + OBJ + Theory = 100)
# ==============================================================================
@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    """
    Admin for Exam Results
    Nigerian School Format: CA1(15) + CA2(15) + OBJ(30) + Theory(40) = 100
    
    Grading Scale:
    - A: 75-100 (Excellent)
    - B: 70-74 (Very Good)
    - C: 60-69 (Good)
    - D: 50-59 (Pass)
    - E: 45-49 (Fair)
    - F: 0-44 (Fail)
    """
    list_display = (
        'get_admission_number', 'get_student_name', 'subject',
        'session', 'term',
        'ca1_score', 'ca2_score', 'obj_score', 'theory_score',
        'total_score', 'grade', 'position',
        'cumulative_score', 'cumulative_grade'
    )
    list_filter = ('session', 'term', 'grade', 'subject', 'student__class_level')
    search_fields = (
        'student__admission_number',
        'student__first_name',
        'student__last_name',
        'subject__name'
    )
    ordering = ('-uploaded_at',)
    readonly_fields = (
        'total_score', 'grade', 'remark',
        'cumulative_score', 'cumulative_grade',
        'uploaded_at', 'updated_at'
    )
    raw_id_fields = ('student', 'subject')
    
    fieldsets = (
        ('Student & Subject', {
            'fields': ('student', 'subject', 'session', 'term')
        }),
        ('Score Components (Nigerian School Format)', {
            'fields': (
                ('ca1_score', 'ca2_score'),
                ('obj_score', 'theory_score'),
            ),
            'description': '''
            Nigerian Secondary School Grading:
            • CA1: Max 15 marks (manual entry)
            • CA2: Max 15 marks (manual entry)
            • OBJ/CBT: Max 30 marks (from CBT system)
            • Theory: Max 40 marks (manual entry)
            • Total: 100 marks
            '''
        }),
        ('Calculated Results (Auto-generated)', {
            'fields': ('total_score', 'grade', 'remark'),
            'classes': ('collapse',)
        }),
        ('Class Statistics', {
            'fields': ('position', 'class_average', 'total_students', 'highest_score', 'lowest_score'),
            'classes': ('collapse',)
        }),
        ('Cumulative Scores (For Report Cards)', {
            'fields': (
                ('first_term_total', 'second_term_total', 'third_term_total'),
                ('cumulative_score', 'cumulative_grade')
            ),
            'classes': ('collapse',)
        }),
        ('CBT Metadata', {
            'fields': ('total_obj_questions', 'submitted_at'),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('uploaded_by', 'uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Admission No.', ordering='student__admission_number')
    def get_admission_number(self, obj):
        return obj.student.admission_number

    @admin.display(description='Student Name')
    def get_student_name(self, obj):
        return obj.student.full_name


# ==============================================================================
# PROMOTION RULE ADMIN
# ==============================================================================
@admin.register(PromotionRule)
class PromotionRuleAdmin(admin.ModelAdmin):
    """
    Admin for Promotion Rules
    
    Configurable criteria for student promotion:
    - Pass mark percentage (default 50%)
    - Compulsory subjects (default: Math, English)
    - Minimum additional subjects (default: 5)
    """
    list_display = (
        'session', 'class_level', 'pass_mark_percentage',
        'get_compulsory_count', 'minimum_additional_subjects',
        'promotion_mode', 'is_active'
    )
    list_filter = ('session', 'class_level', 'promotion_mode', 'is_active')
    search_fields = ('session__name',)
    ordering = ('-session__start_date', 'class_level__order')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Scope', {
            'fields': ('session', 'class_level'),
            'description': 'Leave class level blank to apply to all classes.'
        }),
        ('Pass Requirements', {
            'fields': (
                'pass_mark_percentage',
                'compulsory_subject_ids',
                'minimum_additional_subjects',
            ),
            'description': '''
            Default Nigerian criteria:
            • Pass mark: 50%
            • Compulsory: Mathematics + English Language
            • Additional: 5 other subjects
            • Total minimum: 7 subjects
            '''
        }),
        ('Promotion Mode', {
            'fields': ('promotion_mode',),
            'description': '''
            • Auto: System decides based on rules
            • Recommend: System suggests, admin approves
            • Manual: Admin decides for each student
            '''
        }),
        ('Carryover Settings', {
            'fields': ('allow_carryover', 'max_carryover_subjects'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Compulsory Subjects')
    def get_compulsory_count(self, obj):
        return len(obj.compulsory_subject_ids) if obj.compulsory_subject_ids else 0