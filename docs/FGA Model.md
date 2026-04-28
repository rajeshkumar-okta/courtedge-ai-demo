model
  schema 1.1

type user

type agent
  relations
    define acts_for: [user]

type delegation
  relations
    define agent: [agent]
    define principal: [user]

type clearance_level
  relations
    define granted_to: [user]
    define holder: granted_to or holder from next_higher
    define next_higher: [clearance_level]

type inventory_system
  relations
    define active_delegation: [delegation with agent_request_valid]
    define active_manager: manager but not on_vacation
    define can_manage: active_manager
    define can_manage_via_delegation: active_manager and delegated_principal
    define delegated_principal: principal from active_delegation
    define manager: [user]
    define on_vacation: [user]

type inventory_item
  relations
    define can_update: has_clearance and can_manage from parent
    define can_update_via_delegation: has_clearance and can_manage_via_delegation from parent
    define can_view: can_manage from parent
    define can_view_via_delegation: can_manage_via_delegation from parent
    define has_clearance: holder from required_clearance
    define parent: [inventory_system]
    define required_clearance: [clearance_level]

condition agent_request_valid(budget_limit: int, current_time: timestamp, delegation_end: timestamp, delegation_purpose: string, delegation_start: timestamp, request_amount: int, request_purpose: string) {
  current_time >= delegation_start && current_time <= delegation_end && request_purpose == delegation_purpose && request_amount <= budget_limit
}
