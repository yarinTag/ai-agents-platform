"""Repository composition: the only place that connects storage collaborators."""
from .settings import SettingsRepository
from .agents import AgentsRepository
from .templates import TemplatesRepository
from .maintenance import MaintenanceRepository
from .projects import ProjectsRepository
from .skills import SkillsRepository
from .tasks import TasksRepository
from .events import EventsRepository
from .audit import AuditRepository
from .schedules import SchedulesRepository
from .interactions import InteractionsRepository
from .sessions import SessionsRepository
from .chat import ChatRepository
from .memory import MemoryRepository
from .war_room import WarRoomRepository
from .messages import MessagesRepository
from .super_agents import SuperAgentsRepository
from .connectors import ConnectorsRepository
from .tool_calls import ToolCallsRepository
from .agent_permissions import AgentPermissionsRepository
from .teams import TeamsRepository
from .departments import DepartmentsRepository
from .organizations import OrganizationsRepository
from .department_permissions import DepartmentPermissionsRepository
from .users import UsersRepository
from .invitations import InvitationsRepository
from .workflows import WorkflowsRepository


def configure_repositories(manager):
    manager._settings = SettingsRepository(
        manager._get_connection
    )
    manager._agents = AgentsRepository(
        manager._get_connection,
        create_agent_session=lambda *args, **kwargs: manager.create_agent_session(*args, **kwargs),
        max_agents=lambda: manager.max_agents
    )
    manager._templates = TemplatesRepository(
        manager._get_connection
    )
    manager._maintenance = MaintenanceRepository(
        manager._get_connection,
        _seed_default_agents=lambda *args, **kwargs: manager._seed_default_agents(*args, **kwargs),
        _seed_default_templates=lambda *args, **kwargs: manager._seed_default_templates(*args, **kwargs)
    )
    manager._projects = ProjectsRepository(
        manager._get_connection
    )
    manager._skills = SkillsRepository(
        manager._get_connection
    )
    manager._tasks = TasksRepository(
        manager._get_connection
    )
    manager._events = EventsRepository(
        manager._get_connection
    )
    manager._audit = AuditRepository(
        manager._get_connection
    )
    manager._schedules = SchedulesRepository(
        manager._get_connection
    )
    manager._interactions = InteractionsRepository(
        manager._get_connection
    )
    manager._sessions = SessionsRepository(
        manager._get_connection,
        get_agent=lambda *args, **kwargs: manager.get_agent(*args, **kwargs)
    )
    manager._chat = ChatRepository(
        manager._get_connection
    )
    manager._memory = MemoryRepository(
        manager._get_connection
    )
    manager._war_room = WarRoomRepository(
        manager._get_connection
    )
    manager._messages = MessagesRepository(
        manager._get_connection
    )
    manager._super_agents = SuperAgentsRepository(
        manager._get_connection
    )
    manager._connectors = ConnectorsRepository(
        manager._get_connection
    )
    manager._tool_calls = ToolCallsRepository(
        manager._get_connection
    )
    manager._agent_permissions = AgentPermissionsRepository(
        manager._get_connection,
        get_agent=lambda *args, **kwargs: manager.get_agent(*args, **kwargs)
    )
    manager._teams = TeamsRepository(
        manager._get_connection
    )
    manager._departments = DepartmentsRepository(
        manager._get_connection
    )
    manager._organizations = OrganizationsRepository(
        manager._get_connection
    )
    manager._department_permissions = DepartmentPermissionsRepository(
        manager._get_connection,
        get_department=lambda *args, **kwargs: manager.get_department(*args, **kwargs)
    )
    manager._users = UsersRepository(
        manager._get_connection
    )
    manager._invitations = InvitationsRepository(
        manager._get_connection,
        add_user_to_department=lambda *args, **kwargs: manager.add_user_to_department(*args, **kwargs),
        create_user=lambda *args, **kwargs: manager.create_user(*args, **kwargs),
        get_user_by_email=lambda *args, **kwargs: manager.get_user_by_email(*args, **kwargs),
        update_user=lambda *args, **kwargs: manager.update_user(*args, **kwargs)
    )
    manager._workflows = WorkflowsRepository(
        manager._get_connection
    )
