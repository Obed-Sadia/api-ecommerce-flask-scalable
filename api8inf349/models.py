from peewee import *
import os

database = PostgresqlDatabase(
    os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT'))
)

class BaseModel(Model):
    class Meta:
        database = database

class Product(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = TextField()
    price = FloatField()
    in_stock = BooleanField(default=True)
    weight = IntegerField()
    image = CharField()

class Order(BaseModel):
    id = AutoField()
    total_price = FloatField(null=True)
    total_price_tax = FloatField(null=True)
    shipping_price = FloatField(null=True)
    email = CharField(null=True)
    shipping_country = CharField(null=True)
    shipping_address = CharField(null=True)
    shipping_postal_code = CharField(null=True)
    shipping_city = CharField(null=True)
    shipping_province = CharField(null=True)
    paid = BooleanField(default=False)
    credit_card_name = CharField(null=True)
    credit_card_first_digits = CharField(null=True)
    credit_card_last_digits = CharField(null=True)
    credit_card_expiration_year = IntegerField(null=True)
    credit_card_expiration_month = IntegerField(null=True)
    transaction_id = CharField(null=True)
    transaction_success = BooleanField(null=True)
    transaction_amount = FloatField(null=True)
    transaction_error_code = CharField(null=True)
    transaction_error_name = CharField(null=True)
    is_processing = BooleanField(default=False)

class OrderProduct(BaseModel):
    order = ForeignKeyField(Order, backref='orderproducts')
    product = ForeignKeyField(Product)
    quantity = IntegerField()