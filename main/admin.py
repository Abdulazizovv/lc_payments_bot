from django.contrib import admin
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

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
    list_display = ("chat_id", "title", "monthly_fee", "is_active", "student_count", "created_at")
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
            "fields": ("title", "description", "chat_id")
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
    change_list_template = "admin/main/payment/change_list.html"

    list_display = ("enrollment", "student", "group", "amount", "month", "paid_at", "creator")
    list_filter = ("enrollment__group", "enrollment__student", "created_by", "month", "paid_at")
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

    @admin.display(ordering="created_by", description="Created by")
    def creator(self, obj):
        return obj.created_by or "—"

    def _fmt(self, n: int) -> str:
        try:
            return f"{int(n):,}".replace(",", " ")
        except Exception:
            return str(n)

    def _month_start(self, dt):
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _parse_target_month(self, s: str | None, default_dt):
        if not s:
            dt = default_dt
        else:
            try:
                year, month = map(int, s.split("-"))
                dt = default_dt.replace(year=year, month=month)
            except Exception:
                dt = default_dt
        return self._month_start(dt)

    def get_report_data(self, request):
        now = timezone.now()
        cur_m = self._month_start(now)
        sel_m = self._parse_target_month(request.GET.get("target_month"), now)

        # Filters from sidebar
        group_id = request.GET.get("enrollment__group__id__exact")
        student_id = request.GET.get("enrollment__student__id__exact")

        enr_qs = Enrollment.objects.filter(is_active=True)
        if group_id:
            enr_qs = enr_qs.filter(group_id=group_id)
        # If student filter applied, restrict to that student's active enrollments
        if student_id:
            enr_qs = enr_qs.filter(student_id=student_id)

        expected_current = enr_qs.aggregate(total=Coalesce(Sum("monthly_fee"), 0))["total"] or 0
        expected_selected = expected_current if sel_m == cur_m else enr_qs.aggregate(total=Coalesce(Sum("monthly_fee"), 0))["total"] or 0

        pay_sel = Payment.objects.filter(month=sel_m.date())
        pay_cur = Payment.objects.filter(month=cur_m.date())
        if group_id:
            pay_sel = pay_sel.filter(enrollment__group_id=group_id)
            pay_cur = pay_cur.filter(enrollment__group_id=group_id)
        if student_id:
            pay_sel = pay_sel.filter(enrollment__student_id=student_id)
            pay_cur = pay_cur.filter(enrollment__student_id=student_id)

        collected_selected = pay_sel.aggregate(total=Coalesce(Sum("amount"), 0))["total"] or 0
        collected_current = pay_cur.aggregate(total=Coalesce(Sum("amount"), 0))["total"] or 0

        data = {
            "current_month_str": f"{cur_m.year:04d}-{cur_m.month:02d}",
            "selected_month_str": f"{sel_m.year:04d}-{sel_m.month:02d}",
            "expected_current": self._fmt(expected_current),
            "collected_current": self._fmt(collected_current),
            "expected_selected": self._fmt(expected_selected),
            "collected_selected": self._fmt(collected_selected),
        }
        return data

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        try:
            extra_context["report"] = self.get_report_data(request)
        except Exception:
            # Fallback if something goes wrong; avoid breaking admin
            extra_context["report"] = None
        return super().changelist_view(request, extra_context=extra_context)


# Admin site titles
admin.site.site_header = "LC Payments Administration"
admin.site.site_title = "LC Payments Admin"
admin.site.index_title = "Dashboard"
