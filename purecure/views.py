from datetime import date, datetime
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django import forms
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import (
    Customers, Employees, MedicineBatches, MedicineCategories, Medicines, Payments,
    PrescriptionItems, Prescriptions, PurchaseItems, Purchases, Roles, SaleItems,
    Sales, StockMovements, Suppliers,
)


ALL_ROLES = {"Manager", "Pharmacist", "Cashier"}
TABLES = {
    "customers": ("Customers", Customers, ["customer_id", "first_name", "last_name", "phone", "email", "created_at"], ALL_ROLES),
    "medicines": ("Medicines", Medicines, ["medicine_id", "medicine_name", "generic_name", "category.category_name", "unit_price", "reorder_level", "is_active"], ALL_ROLES),
    "medicine-categories": ("Medicine categories", MedicineCategories, ["category_id", "category_name", "description"], {"Manager", "Pharmacist"}),
    "medicine-batches": ("Medicine batches", MedicineBatches, ["batch_id", "medicine.medicine_name", "batch_number", "expiry_date", "quantity_remaining", "unit_cost"], {"Manager", "Pharmacist"}),
    "suppliers": ("Suppliers", Suppliers, ["supplier_id", "supplier_name", "contact_person", "phone", "email", "is_active"], {"Manager", "Pharmacist"}),
    "purchases": ("Purchases", Purchases, ["purchase_id", "supplier.supplier_name", "employee.username", "purchase_date", "invoice_number", "status"], {"Manager", "Pharmacist"}),
    "purchase-items": ("Purchase items", PurchaseItems, ["purchase_item_id", "purchase.purchase_id", "medicine.medicine_name", "quantity", "unit_cost", "batch_number", "expiry_date"], {"Manager", "Pharmacist"}),
    "stock-movements": ("Stock movements", StockMovements, ["movement_id", "medicine.medicine_name", "batch.batch_number", "employee.username", "movement_type", "quantity", "movement_date"], {"Manager", "Pharmacist"}),
    "sales": ("Sales", Sales, ["sale_id", "customer.first_name", "employee.username", "sale_date", "total_amount", "status"], ALL_ROLES),
    "sale-items": ("Sale items", SaleItems, ["sale_item_id", "sale.sale_id", "medicine.medicine_name", "batch.batch_number", "quantity", "unit_price", "subtotal"], ALL_ROLES),
    "payments": ("Payments", Payments, ["payment_id", "sale.sale_id", "amount", "payment_date", "payment_method", "payment_status", "reference_number"], ALL_ROLES),
    "prescriptions": ("Prescriptions", Prescriptions, ["prescription_id", "customer.first_name", "employee.username", "prescriber_name", "prescription_date", "status"], {"Manager", "Pharmacist"}),
    "prescription-items": ("Prescription items", PrescriptionItems, ["prescription_item_id", "prescription.prescription_id", "medicine.medicine_name", "prescribed_quantity", "dosage", "frequency", "quantity_dispensed"], {"Manager", "Pharmacist"}),
    "employees": ("Employees", Employees, ["employee_id", "role.role_name", "first_name", "last_name", "username", "phone", "email", "is_active"], {"Manager"}),
    "roles": ("Roles", Roles, ["role_id", "role_name", "description"], {"Manager"}),
}

# Create/edit rights are narrower than read access for transaction and audit tables.
CREATE_ROLES = {
    "customers": ALL_ROLES,
    "medicines": {"Manager", "Pharmacist"},
    "medicine-categories": {"Manager", "Pharmacist"},
    "suppliers": {"Manager", "Pharmacist"},
    "purchases": {"Manager", "Pharmacist"},
    "employees": {"Manager"},
}
EDIT_ROLES = {
    "customers": ALL_ROLES,
    "medicines": {"Manager", "Pharmacist"},
    "medicine-categories": {"Manager", "Pharmacist"},
    "suppliers": {"Manager", "Pharmacist"},
    "employees": {"Manager"},
}


def current_employee(request):
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return None
    return Employees.objects.select_related("role").filter(employee_id=employee_id, is_active=1).first()


def employee_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        employee = current_employee(request)
        if not employee:
            request.session.flush()
            return redirect("login")
        request.employee = employee
        return view(request, *args, **kwargs)
    return wrapped


def labels(field_names):
    return [field.replace("_id", "").replace("_", " ").replace(".", " · ").title() for field in field_names]


def display_value(instance, field_path):
    value = instance
    for field in field_path.split("."):
        value = getattr(value, field, None)
        if value is None:
            return "—"
    if isinstance(value, Decimal):
        return f"Shs {value:,.2f}"
    if isinstance(value, (datetime, date)):
        return value.strftime("%d %b %Y")
    if field_path == "is_active":
        return "Active" if value else "Inactive"
    return str(value) or "—"


def nav_items(role_name):
    return [{"slug": slug, "label": title} for slug, (title, _model, _fields, roles) in TABLES.items() if role_name in roles]


def filter_records(queryset, model, fields, query):
    if not query:
        return queryset
    search = Q()
    if query.isdigit():
        search |= Q(pk=int(query))
    for path in fields:
        current_model = model
        try:
            for segment in path.split("."):
                field = current_model._meta.get_field(segment)
                if field.is_relation:
                    current_model = field.related_model
                    continue
                field_type = field.get_internal_type()
                lookup = path.replace(".", "__")
                if field_type in {"CharField", "TextField", "EmailField", "SlugField"}:
                    search |= Q(**{f"{lookup}__icontains": query})
                elif query.isdigit() and field_type in {"AutoField", "BigAutoField", "SmallAutoField", "IntegerField", "BigIntegerField", "PositiveIntegerField", "PositiveSmallIntegerField"}:
                    search |= Q(**{lookup: int(query)})
                elif field_type in {"DecimalField", "FloatField"}:
                    try:
                        search |= Q(**{lookup: Decimal(query)})
                    except Exception:
                        pass
                break
        except Exception:
            continue
    return queryset.filter(search)


def matches_password(raw_password, stored_password):
    if stored_password.startswith(("pbkdf2_", "argon2$", "bcrypt$", "scrypt$")):
        return check_password(raw_password, stored_password)
    return constant_time_compare(raw_password, stored_password)


def login(request):
    if current_employee(request):
        return redirect("dashboard")
    if request.method == "POST":
        employee = Employees.objects.select_related("role").filter(username=request.POST.get("username", "").strip(), is_active=1).first()
        if employee and matches_password(request.POST.get("password", ""), employee.password_hash):
            request.session.cycle_key()
            request.session["employee_id"] = employee.employee_id
            return redirect("dashboard")
        messages.error(request, "Incorrect username or password.")
    return render(request, "purecure/login.html")


@employee_required
def logout(request):
    request.session.flush()
    return redirect("login")


@employee_required
def dashboard(request):
    role_name = request.employee.role.role_name
    return render(request, "purecure/dashboard.html", {
        "employee": request.employee, "nav_items": nav_items(role_name),
        "medicine_count": Medicines.objects.filter(is_active=1).count(),
        "customer_count": Customers.objects.count(), "sale_count": Sales.objects.count(),
        "stock_total": MedicineBatches.objects.aggregate(total=Coalesce(Sum("quantity_remaining"), 0))["total"],
        "recent_sales": Sales.objects.select_related("customer", "employee").order_by("-sale_date")[:6],
    })


@employee_required
def records(request, table_name):
    table = TABLES.get(table_name)
    if not table:
        return redirect("dashboard")
    title, model, fields, allowed_roles = table
    role_name = request.employee.role.role_name
    if role_name not in allowed_roles:
        messages.error(request, "Your role does not have access to that section.")
        return redirect("dashboard")
    query = request.GET.get("q", "").strip()
    instances = filter_records(model.objects.select_related().all(), model, fields, query).order_by("pk")[:100]
    rows = [{"pk": instance.pk, "cells": [display_value(instance, field) for field in fields]} for instance in instances]
    sale_rows = []
    if table_name == "sales":
        sale_rows = list(instances)
    return render(request, "purecure/records.html", {
        "employee": request.employee, "nav_items": nav_items(role_name), "title": title,
        "headers": labels(fields), "rows": rows, "table_name": table_name,
        "can_add": role_name in CREATE_ROLES.get(table_name, set()),
        "can_edit": role_name in EDIT_ROLES.get(table_name, set()),
        "can_record_sale": table_name == "sales" and role_name in {"Manager", "Pharmacist"},
        "sale_rows": sale_rows,
        "can_prepare_sale": role_name in {"Manager", "Pharmacist"},
        "can_take_payment": role_name in {"Manager", "Cashier"},
        "query": query,
    })


@employee_required
def edit_record(request, table_name, pk):
    table = TABLES.get(table_name)
    if not table:
        return redirect("dashboard")
    title, model, _fields, allowed_roles = table
    role_name = request.employee.role.role_name
    if role_name not in allowed_roles or role_name not in EDIT_ROLES.get(table_name, set()):
        messages.error(request, "Your role does not have access to that section.")
        return redirect("dashboard")
    instance = model.objects.filter(pk=pk).first()
    if instance is None:
        messages.error(request, "That record could not be found.")
        return redirect("records", table_name=table_name)

    editable_fields = [
        field.name for field in model._meta.concrete_fields
        if not field.primary_key and field.name not in {"password_hash", "created_at"}
    ]
    EditForm = type("EditForm", (forms.ModelForm,), {
        "Meta": type("Meta", (), {"model": model, "fields": editable_fields})
    })
    form = EditForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Record updated successfully.")
        return redirect("records", table_name=table_name)
    return render(request, "purecure/edit_record.html", {
        "employee": request.employee, "nav_items": nav_items(role_name),
        "title": title, "table_name": table_name, "form": form, "instance": instance,
    })


@employee_required
def add_record(request, table_name):
    table = TABLES.get(table_name)
    if not table:
        return redirect("dashboard")
    title, model, _fields, allowed_roles = table
    role_name = request.employee.role.role_name
    if role_name not in allowed_roles or role_name not in CREATE_ROLES.get(table_name, set()):
        messages.error(request, "Your role cannot add records in that section.")
        return redirect("dashboard")

    if table_name == "purchases":
        return redirect("record_purchase")
    if table_name == "employees":
        class EmployeeForm(forms.ModelForm):
            password = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Temporary password")

            class Meta:
                model = Employees
                fields = ["role", "first_name", "last_name", "phone", "email", "username", "is_active"]

        form = EmployeeForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            employee = form.save(commit=False)
            employee.password_hash = make_password(form.cleaned_data["password"])
            employee.created_at = timezone.now()
            employee.save()
            messages.success(request, "Employee account created.")
            return redirect("records", table_name=table_name)
    else:
        add_fields = {
            "customers": ["first_name", "last_name", "date_of_birth", "gender", "phone", "email", "address"],
            "medicines": ["category", "medicine_name", "generic_name", "unit_price", "reorder_level", "description", "is_active"],
            "medicine-categories": ["category_name", "description"],
            "suppliers": ["supplier_name", "registration_number", "contact_person", "phone", "email", "address", "is_active"],
        }[table_name]
        AddForm = type("AddForm", (forms.ModelForm,), {
            "Meta": type("Meta", (), {"model": model, "fields": add_fields})
        })
        form = AddForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            record = form.save(commit=False)
            if hasattr(record, "created_at"):
                record.created_at = timezone.now()
            record.save()
            messages.success(request, f"{title[:-1]} added successfully.")
            return redirect("records", table_name=table_name)
    return render(request, "purecure/edit_record.html", {
        "employee": request.employee, "nav_items": nav_items(role_name),
        "title": f"Add {title[:-1]}", "table_name": table_name, "form": form,
    })


class SaleForm(forms.Form):
    customer = forms.ModelChoiceField(queryset=Customers.objects.all(), required=False, empty_label="Walk-in customer")
    batch = forms.ModelChoiceField(queryset=MedicineBatches.objects.none(), label="Medicine batch")
    quantity = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = MedicineBatches.objects.filter(quantity_remaining__gt=0, expiry_date__gte=timezone.localdate(), medicine__is_active=1).select_related("medicine")
        self.fields["batch"].label_from_instance = lambda batch: f"{batch.medicine.medicine_name} · {batch.batch_number} · {batch.quantity_remaining} available · Shs {batch.medicine.unit_price}"


class PurchaseForm(forms.Form):
    supplier = forms.ModelChoiceField(queryset=Suppliers.objects.none())
    medicine = forms.ModelChoiceField(queryset=Medicines.objects.none())
    quantity = forms.IntegerField(min_value=1)
    unit_cost = forms.DecimalField(min_value=Decimal("0.01"), max_digits=10, decimal_places=2)
    batch_number = forms.CharField(max_length=100)
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    invoice_number = forms.CharField(max_length=100, required=False, label="Supplier invoice number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Suppliers.objects.filter(is_active=1).order_by("supplier_name")
        self.fields["medicine"].queryset = Medicines.objects.filter(is_active=1).order_by("medicine_name")

    def clean_expiry_date(self):
        expiry = self.cleaned_data["expiry_date"]
        if expiry < timezone.localdate():
            raise forms.ValidationError("The batch expiry date must be today or later.")
        return expiry

    def clean_invoice_number(self):
        invoice = self.cleaned_data.get("invoice_number")
        if invoice and Purchases.objects.filter(invoice_number=invoice).exists():
            raise forms.ValidationError("A purchase with this invoice number already exists.")
        return invoice or None

    def clean(self):
        cleaned = super().clean()
        medicine = cleaned.get("medicine")
        batch_number = cleaned.get("batch_number")
        if medicine and batch_number and MedicineBatches.objects.filter(medicine=medicine, batch_number=batch_number).exists():
            self.add_error("batch_number", "This batch number is already recorded for the selected medicine.")
        return cleaned


@employee_required
def record_purchase(request):
    if request.employee.role.role_name not in {"Manager", "Pharmacist"}:
        messages.error(request, "Only a pharmacist or manager can record received purchases.")
        return redirect("dashboard")
    form = PurchaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                purchase = Purchases.objects.create(
                    supplier=data["supplier"], employee=request.employee,
                    purchase_date=timezone.now(), invoice_number=data["invoice_number"], status="Received",
                )
                PurchaseItems.objects.create(
                    purchase=purchase, medicine=data["medicine"], quantity=data["quantity"],
                    unit_cost=data["unit_cost"], batch_number=data["batch_number"], expiry_date=data["expiry_date"],
                )
                batch = MedicineBatches.objects.create(
                    medicine=data["medicine"], purchase=purchase, batch_number=data["batch_number"],
                    expiry_date=data["expiry_date"], quantity_received=data["quantity"],
                    quantity_remaining=data["quantity"], unit_cost=data["unit_cost"],
                    received_date=timezone.localdate(),
                )
                StockMovements.objects.create(
                    medicine=data["medicine"], batch=batch, employee=request.employee,
                    movement_type="Purchase", quantity=data["quantity"], movement_date=timezone.now(),
                    reference_type="Purchase", reference_id=purchase.pk,
                    notes=f"Received purchase #{purchase.pk}",
                )
        except IntegrityError:
            form.add_error(None, "The purchase could not be saved. Check that the invoice and batch numbers are unique.")
        else:
            messages.success(request, f"Purchase #{purchase.pk} recorded and stock updated.")
            return redirect("records", table_name="purchases")
    return render(request, "purecure/edit_record.html", {
        "employee": request.employee, "nav_items": nav_items(request.employee.role.role_name),
        "title": "Record received purchase", "table_name": "purchases", "form": form,
        "form_heading": "Record a received purchase",
        "form_description": "Enter the supplier invoice and batch details. Stock will be added when you save.",
        "submit_label": "Save purchase and receive stock",
    })


@employee_required
def record_sale(request):
    if request.employee.role.role_name not in {"Manager", "Pharmacist"}:
        messages.error(request, "Only a pharmacist or manager can prepare a sale.")
        return redirect("dashboard")
    form = SaleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        batch = form.cleaned_data["batch"]
        quantity = form.cleaned_data["quantity"]
        with transaction.atomic():
            batch = MedicineBatches.objects.select_for_update().select_related("medicine").get(pk=batch.pk)
            if quantity > batch.quantity_remaining:
                form.add_error("quantity", f"Only {batch.quantity_remaining} units remain in this batch.")
            else:
                medicine = batch.medicine
                total = medicine.unit_price * quantity
                sale = Sales.objects.create(
                    customer=form.cleaned_data["customer"], employee=request.employee,
                    sale_date=timezone.now(), total_amount=total, status="Pending Payment",
                )
                SaleItems.objects.create(sale=sale, medicine=medicine, batch=batch, quantity=quantity,
                                         unit_price=medicine.unit_price, subtotal=total)
                messages.success(request, f"Receipt #{sale.pk} prepared. Take it to the cashier for payment.")
                return redirect("sale_receipt", sale_id=sale.pk)
    return render(request, "purecure/edit_record.html", {
        "employee": request.employee, "nav_items": nav_items(request.employee.role.role_name),
        "title": "Record a sale", "table_name": "sales", "form": form,
    })


@employee_required
def sale_receipt(request, sale_id):
    sale = Sales.objects.select_related("customer", "employee").filter(pk=sale_id).first()
    if not sale:
        messages.error(request, "Sale receipt not found.")
        return redirect("records", table_name="sales")
    items = SaleItems.objects.filter(sale=sale).select_related("medicine", "batch")
    payment = Payments.objects.filter(sale=sale).order_by("-payment_id").first()
    return render(request, "purecure/receipt.html", {
        "employee": request.employee, "nav_items": nav_items(request.employee.role.role_name),
        "sale": sale, "items": items, "payment": payment,
        "change_due": max(payment.amount - sale.total_amount, Decimal("0.00")) if payment else None,
        "can_take_payment": request.employee.role.role_name in {"Manager", "Cashier"} and sale.status == "Pending Payment",
    })


class PaymentForm(forms.Form):
    payment_method = forms.ChoiceField(choices=[("Cash", "Cash"), ("Card", "Card"), ("Mobile Money", "Mobile Money"), ("Insurance", "Insurance")])
    amount_received = forms.DecimalField(min_value=Decimal("0.01"), max_digits=10, decimal_places=2, label="Amount received")

    def __init__(self, *args, sale_total, **kwargs):
        self.sale_total = sale_total
        super().__init__(*args, **kwargs)

    def clean_amount_received(self):
        received = self.cleaned_data["amount_received"]
        if received < self.sale_total:
            raise forms.ValidationError(f"Amount received must be at least Shs {self.sale_total:,.2f}.")
        return received


@employee_required
def take_payment(request, sale_id):
    if request.employee.role.role_name not in {"Manager", "Cashier"}:
        messages.error(request, "Only a cashier or manager can complete payment.")
        return redirect("sale_receipt", sale_id=sale_id)
    sale_for_form = Sales.objects.filter(pk=sale_id, status="Pending Payment").first()
    if not sale_for_form:
        messages.error(request, "This sale has already been completed or cannot be found.")
        return redirect("records", table_name="sales")
    form = PaymentForm(request.POST or None, sale_total=sale_for_form.total_amount)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            sale = Sales.objects.select_for_update().filter(pk=sale_id).first()
            if not sale or sale.status != "Pending Payment":
                messages.error(request, "This sale has already been completed or cannot be found.")
                return redirect("records", table_name="sales")
            items = list(SaleItems.objects.filter(sale=sale).select_related("medicine", "batch"))
            batches = {b.pk: b for b in MedicineBatches.objects.select_for_update().filter(pk__in=[i.batch_id for i in items])}
            for item in items:
                batch = batches.get(item.batch_id)
                if not batch or batch.quantity_remaining < item.quantity or batch.expiry_date < timezone.localdate():
                    messages.error(request, f"Insufficient or expired stock for {item.medicine.medicine_name}; sale was not completed.")
                    return redirect("sale_receipt", sale_id=sale_id)
            for item in items:
                batch = batches[item.batch_id]
                batch.quantity_remaining -= item.quantity
                batch.save(update_fields=["quantity_remaining"])
                StockMovements.objects.create(
                    medicine=item.medicine, batch=batch, employee=request.employee,
                    movement_type="Sale", quantity=item.quantity, movement_date=timezone.now(),
                    reference_type="Sale", reference_id=sale.pk, notes=f"Sale #{sale.pk}",
                )
            payment = Payments.objects.create(
                sale=sale, amount=form.cleaned_data["amount_received"], payment_date=timezone.now(),
                payment_method=form.cleaned_data["payment_method"], payment_status="Paid",
            )
            payment.reference_number = f"PC-{payment.payment_id:08d}"
            payment.save(update_fields=["reference_number"])
            sale.status = "Completed"
            sale.save(update_fields=["status"])
        messages.success(request, f"Payment recorded for sale #{sale.pk}. The customer may collect their medicine.")
        return redirect("sale_receipt", sale_id=sale.pk)
    sale = sale_for_form
    return render(request, "purecure/payment.html", {
        "employee": request.employee, "nav_items": nav_items(request.employee.role.role_name),
        "sale": sale, "form": form,
    })
