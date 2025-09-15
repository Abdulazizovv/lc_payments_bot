from django.db import models
from django.utils import timezone


class Group(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    monthly_fee = models.BigIntegerField(default=0)
    chat_id = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title
    

class Student(models.Model):
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    groups = models.ManyToManyField(Group, through="Enrollment", related_name='students')
    
    def __str__(self):
        return self.full_name
    

class Enrollment(models.Model):
    student: "Student" = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    group: "Group" = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='enrollments')
    chat_id = models.CharField(max_length=255, null=True, blank=True)
    monthly_fee = models.BigIntegerField(default=0)
    joined_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.monthly_fee:
            self.monthly_fee = self.group.monthly_fee
        if not self.chat_id:
            self.chat_id = self.group.chat_id
        super().save(*args, **kwargs)
    

class Payment(models.Model):
    enrollment: "Enrollment" = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='payments')
    amount = models.BigIntegerField()
    month = models.DateField() # Represents the month for which the payment is made
    paid_at = models.DateTimeField(auto_now_add=True)
    