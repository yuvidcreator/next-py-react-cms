"""Built-in Hook Definitions — all core hook names as constants."""


class CoreHooks:
    # ── Application Lifecycle ────────────────────────────────
    PYPRESS_INIT = "pypress_init"
    PYPRESS_LOADED = "pypress_loaded"
    PYPRESS_SHUTDOWN = "pypress_shutdown"

    # ── Plugin Lifecycle ─────────────────────────────────────
    PLUGINS_LOADED = "plugins_loaded"
    PLUGIN_ACTIVATED = "plugin_activated"
    PLUGIN_DEACTIVATED = "plugin_deactivated"

    # ── Theme Lifecycle ──────────────────────────────────────
    AFTER_SETUP_THEME = "after_setup_theme"
    SWITCH_THEME = "switch_theme"

    # ── Post Actions ─────────────────────────────────────────
    BEFORE_SAVE_POST = "before_save_post"
    SAVE_POST = "save_post"
    AFTER_SAVE_POST = "after_save_post"
    BEFORE_DELETE_POST = "before_delete_post"
    DELETE_POST = "delete_post"
    TRANSITION_POST_STATUS = "transition_post_status"

    # ── Comment Actions ──────────────────────────────────────
    COMMENT_POST = "comment_post"
    EDIT_COMMENT = "edit_comment"
    TRASH_COMMENT = "trash_comment"

    # ── User Actions ─────────────────────────────────────────
    USER_REGISTER = "user_register"
    PROFILE_UPDATE = "profile_update"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # ── Auth Actions ─────────────────────────────────────────
    BEFORE_LOGIN = "before_login"
    AFTER_LOGIN = "after_login"
    FAILED_LOGIN = "failed_login"
    BEFORE_OAUTH_LOGIN = "before_oauth_login"
    AFTER_OAUTH_LOGIN = "after_oauth_login"

    # ── Media Actions ────────────────────────────────────────
    ADD_ATTACHMENT = "add_attachment"
    DELETE_ATTACHMENT = "delete_attachment"

    # ── Content Filters ──────────────────────────────────────
    THE_CONTENT = "the_content"
    THE_TITLE = "the_title"
    THE_EXCERPT = "the_excerpt"
    THE_PERMALINK = "the_permalink"

    # ── Query Filters ────────────────────────────────────────
    PRE_GET_POSTS = "pre_get_posts"
    POST_QUERY_ARGS = "post_query_args"
    FOUND_POSTS = "found_posts"

    # ── Auth Filters ─────────────────────────────────────────
    AUTHENTICATE = "authenticate"
    USER_HAS_CAP = "user_has_cap"

    # ── Admin Filters ────────────────────────────────────────
    ADMIN_MENU = "admin_menu"
    ADMIN_INIT = "admin_init"
    DASHBOARD_WIDGETS = "dashboard_widgets"

    # ── REST API Filters ─────────────────────────────────────
    REST_PRE_DISPATCH = "rest_pre_dispatch"
    REST_POST_DISPATCH = "rest_post_dispatch"

    # ── Template Filters ─────────────────────────────────────
    TEMPLATE_INCLUDE = "template_include"
    BODY_CLASS = "body_class"
    WIDGET_AREAS = "widget_areas"

    # ── Option Filters ───────────────────────────────────────
    PRE_UPDATE_OPTION = "pre_update_option"
    OPTION_UPDATED = "option_updated"
