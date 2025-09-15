from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from .models import Group, Student, Enrollment, Payment


# Inlines
class EnrollmentInlineForStudent(admin.TabularInline):
    model = Enrollment
    fk_name = "student"
    extra = 1
    show_change_link = True
    autocomplete_fields = ["group"]


class EnrollmentInlineForGroup(admin.TabularInline):
    model = Enrollment
    fk_name = "group"
    extra = 1
    show_change_link = True
    autocomplete_fields = ["student"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    show_change_link = True
    readonly_fields = ["paid_at"]
    fields = ("amount", "month", "paid_at")


# Group Admin
@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("title", "monthly_fee", "is_active", "student_count", "created_at")
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("title", "description")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [EnrollmentInlineForGroup]
    save_on_top = True
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(student_count_agg=Count("students", distinct=True))

    @admin.display(ordering="student_count_agg", description="Students")
    def student_count(self, obj):
        return obj.student_count_agg

    # Actions
    @admin.action(description="Mark selected groups as Active")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} group(s) marked as active.")

    @admin.action(description="Mark selected groups as Inactive")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} group(s) marked as inactive.")

    actions = ["make_active", "make_inactive"]

    fieldsets = (
        (None, {
            "fields": ("title", "description")
        }),
        ("Finance", {
            "fields": ("monthly_fee",)
        }),
        ("Meta", {
            "fields": ("is_active", "created_at", "updated_at")
        }),
    )


# Student Admin
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone_number", "groups_count")
    search_fields = ("full_name", "phone_number", "enrollments__group__title")
    list_filter = ("enrollments__group",)
    ordering = ("full_name",)
    inlines = [EnrollmentInlineForStudent]
    save_on_top = True
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(groups_count_agg=Count("groups", distinct=True))

    @admin.display(ordering="groups_count_agg", description="Groups")
    def groups_count(self, obj):
        return obj.groups_count_agg

    fieldsets = (
        (None, {
            "fields": ("full_name", "phone_number")
        }),
    )


# Enrollment Admin
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "group",
        "monthly_fee",
        "joined_at",
        "payments_count",
        "total_paid",
    )
    list_filter = ("group", "joined_at")
    search_fields = ("student__full_name", "group__title")
    date_hierarchy = "joined_at"
    ordering = ("-joined_at",)
    list_select_related = ("student", "group")
    inlines = [PaymentInline]
    autocomplete_fields = ("student", "group")
    list_per_page = 50

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            payments_count_agg=Count("payments"),
            total_paid_agg=Coalesce(Sum("payments__amount"), 0),
        )

    @admin.display(ordering="payments_count_agg", description="Payments")
    def payments_count(self, obj):
        return obj.payments_count_agg

    @admin.display(ordering="total_paid_agg", description="Total paid")
    def total_paid(self, obj):
        return obj.total_paid_agg

    fieldsets = (
        (None, {
            "fields": ("student", "group")
        }),
        ("Finance & Dates", {
            "fields": ("monthly_fee", "joined_at")
        }),
    )


# Payment Admin
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "student", "group", "amount", "month", "paid_at")
    list_filter = ("enrollment__group", "enrollment__student", "month", "paid_at")
    search_fields = ("enrollment__student__full_name", "enrollment__group__title")
    date_hierarchy = "paid_at"
    ordering = ("-paid_at",)
    list_select_related = ("enrollment__student", "enrollment__group")
    autocomplete_fields = ("enrollment",)
    readonly_fields = ("paid_at",)
    list_per_page = 50

    @admin.display(ordering="enrollment__student__full_name", description="Student")
    def student(self, obj):
        return obj.enrollment.student

    @admin.display(ordering="enrollment__group__title", description="Group")
    def group(self, obj):
        return obj.enrollment.group


# Admin site titles
admin.site.site_header = "LC Payments Administration"
admin.site.site_title = "LC Payments Admin"
admin.site.index_title = "Dashboard"
