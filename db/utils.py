from db.connection import main_async_session_maker
from db.tables import support_notificationmodel, controller_table, boiler_table, building_table, zip_code_table, \
    users_ownerprofilemodel, users_customuser


async def create_notification(data: dict):
    async with main_async_session_maker() as session:
        notification_statement = support_notificationmodel.insert().values(
            **data
        )
        try:
            await session.execute(notification_statement)
            await session.commit()
        except Exception as e:
            return


async def list_of_controller(serial_numbers: list = None):
    async with main_async_session_maker() as session:
        query = (
            controller_table.select()
            .join(boiler_table)
            .join(users_ownerprofilemodel)
            .join(users_customuser)
            .where(
                controller_table.c.is_statistic.is_(True),
            )
            .with_only_columns(
                controller_table.c.serial_num,
                users_customuser.c.first_name,
                boiler_table.c.id,
                boiler_table.c.name,
            )
        )

        if serial_numbers:
            query = query.where(controller_table.c.serial_num.in_(serial_numbers))

        result_set = await session.execute(query)
        return result_set.fetchall()
