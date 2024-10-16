from sqlalchemy import (
    Table,
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    Text,
    JSON,
    DATETIME,
)

from db.connection import meta


boiler_table = Table(
    'devices_boilermodel',
    meta,
    Column("id", Integer, primary_key=True),
    Column("building_id", ForeignKey("properties_buildingmodel.id")),
    Column("name", String),
    Column("provider_id", ForeignKey("providers_providerprofilemodel.id")),
    extend_existing=True,
)

building_table = Table(
    'properties_buildingmodel',
    meta,
    Column("id", Integer, primary_key=True),
    Column("zip_code_id", ForeignKey("properties_zipcodemodel.id")),
    extend_existing=True,
)

controller_table = Table(
    'devices_ioniqcontrollermodel',
    meta,
    Column("id", Integer, primary_key=True),
    Column("serial_num", String),
    Column("boiler_id", ForeignKey("devices_boilermodel.id")),
    Column("building_id", ForeignKey("properties_buildingmodel.id")),
    Column("systemp_correction_index", Integer, nullable=True),
    Column("owner_id", ForeignKey("users_ownerprofilemodel.id")),
    Column("is_statistic", Boolean),
    extend_existing=True,
)

zip_code_table = Table(
    'properties_zipcodemodel',
    meta,
    Column("id", Integer, primary_key=True),
    Column("todays_temp", Integer),
    extend_existing=True,
)

users_ownerprofilemodel = Table(
    "users_ownerprofilemodel",
    meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", ForeignKey("users_customuser.id")),
    extend_existing=True,
)

users_customuser = Table(
    "users_customuser",
    meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String),
    Column("first_name", String),
    extend_existing=True,
)

users_managerprofilemodel_boilers = Table(
    "users_managerprofilemodel_boilers",
    meta,
    Column("id", Integer, primary_key=True),
    Column("manager_id", ForeignKey("users_managerprofilemodel.id"), primary_key=True),
    Column("boiler_id", ForeignKey("devices_boilermodel.id"), primary_key=True)
)

support_notificationmodel = Table(
    "support_notificationmodel",
    meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("text", Text),
    Column("boiler_id", ForeignKey("devices_boilermodel.id")),
    Column("message_type", String),
    Column("type_id", Integer),
    Column("is_sent", Boolean),
    Column("message_template", String),
    Column("additional_data", JSON, nullable=True),
    Column("updated_at", DATETIME),
    Column("created_at", DATETIME),
    extend_existing=True,
)
