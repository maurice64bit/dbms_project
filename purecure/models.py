# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Customers(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'customers'


class Employees(models.Model):
    employee_id = models.AutoField(primary_key=True)
    role = models.ForeignKey('Roles', models.DO_NOTHING)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(unique=True, max_length=100, blank=True, null=True)
    username = models.CharField(unique=True, max_length=50)
    password_hash = models.CharField(max_length=255)
    is_active = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'employees'


class MedicineBatches(models.Model):
    batch_id = models.AutoField(primary_key=True)
    medicine = models.ForeignKey('Medicines', models.DO_NOTHING)
    purchase = models.ForeignKey('Purchases', models.DO_NOTHING)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()
    quantity_received = models.IntegerField()
    quantity_remaining = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    received_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'medicine_batches'
        unique_together = (('medicine', 'batch_number'),)


class MedicineCategories(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(unique=True, max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'medicine_categories'


class Medicines(models.Model):
    medicine_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(MedicineCategories, models.DO_NOTHING)
    medicine_name = models.CharField(max_length=150)
    generic_name = models.CharField(max_length=150, blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    reorder_level = models.IntegerField()
    description = models.TextField(blank=True, null=True)
    is_active = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'medicines'


class Payments(models.Model):
    payment_id = models.AutoField(primary_key=True)
    sale = models.ForeignKey('Sales', models.DO_NOTHING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField()
    payment_method = models.CharField(max_length=30)
    payment_status = models.CharField(max_length=30)
    reference_number = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payments'


class PrescriptionItems(models.Model):
    prescription_item_id = models.AutoField(primary_key=True)
    prescription = models.ForeignKey('Prescriptions', models.DO_NOTHING)
    medicine = models.ForeignKey(Medicines, models.DO_NOTHING)
    prescribed_quantity = models.IntegerField()
    dosage = models.CharField(max_length=100, blank=True, null=True)
    frequency = models.CharField(max_length=100, blank=True, null=True)
    duration = models.CharField(max_length=100, blank=True, null=True)
    instructions = models.TextField(blank=True, null=True)
    quantity_dispensed = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'prescription_items'


class Prescriptions(models.Model):
    prescription_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customers, models.DO_NOTHING)
    employee = models.ForeignKey(Employees, models.DO_NOTHING)
    prescription_date = models.DateTimeField()
    prescriber_name = models.CharField(max_length=150)
    prescription_reference = models.CharField(unique=True, max_length=100, blank=True, null=True)
    status = models.CharField(max_length=30)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'prescriptions'


class PurchaseItems(models.Model):
    purchase_item_id = models.AutoField(primary_key=True)
    purchase = models.ForeignKey('Purchases', models.DO_NOTHING)
    medicine = models.ForeignKey(Medicines, models.DO_NOTHING)
    quantity = models.IntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'purchase_items'


class Purchases(models.Model):
    purchase_id = models.AutoField(primary_key=True)
    supplier = models.ForeignKey('Suppliers', models.DO_NOTHING)
    employee = models.ForeignKey(Employees, models.DO_NOTHING)
    purchase_date = models.DateTimeField()
    invoice_number = models.CharField(unique=True, max_length=100, blank=True, null=True)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'purchases'


class Roles(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(unique=True, max_length=30)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'roles'


class SaleItems(models.Model):
    sale_item_id = models.AutoField(primary_key=True)
    sale = models.ForeignKey('Sales', models.DO_NOTHING)
    medicine = models.ForeignKey(Medicines, models.DO_NOTHING)
    batch = models.ForeignKey(MedicineBatches, models.DO_NOTHING)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'sale_items'


class Sales(models.Model):
    sale_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customers, models.DO_NOTHING, blank=True, null=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING)
    prescription = models.ForeignKey(Prescriptions, models.DO_NOTHING, blank=True, null=True)
    sale_date = models.DateTimeField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'sales'


class StockMovements(models.Model):
    movement_id = models.AutoField(primary_key=True)
    medicine = models.ForeignKey(Medicines, models.DO_NOTHING)
    batch = models.ForeignKey(MedicineBatches, models.DO_NOTHING)
    employee = models.ForeignKey(Employees, models.DO_NOTHING)
    movement_type = models.CharField(max_length=30)
    quantity = models.IntegerField()
    movement_date = models.DateTimeField()
    reference_type = models.CharField(max_length=50, blank=True, null=True)
    reference_id = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'stock_movements'


class Suppliers(models.Model):
    supplier_id = models.AutoField(primary_key=True)
    supplier_name = models.CharField(max_length=150)
    registration_number = models.CharField(unique=True, max_length=100, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'suppliers'
