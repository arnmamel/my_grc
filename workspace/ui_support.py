from __future__ import annotations

import streamlit as st


def jump_to_page(page: str) -> None:
    st.session_state["workspace_page"] = page
    st.rerun()


def friendly_error_message(exc: Exception, *, fallback: str) -> str:
    message = str(exc).strip()
    if not message:
        return fallback
    normalized = message.lower()
    if "framework binding not found" in normalized:
        return "The selected framework scope is no longer available. Open Portfolio and choose or recreate the correct framework binding."
    if "product not found" in normalized:
        return "The selected product is no longer available. Open Portfolio and confirm the organization and product scope."
    if "control not found" in normalized:
        return "The selected requirement or control is no longer available. Refresh the framework mapping and try again."
    if "not validated" in normalized and "aws profile" in normalized:
        return "The AWS profile still needs a successful AWS SSO login and validation before a live run can continue."
    if isinstance(exc, ValueError):
        return message
    return fallback


def render_navigation_links(links: list[tuple[str, str]], *, key_prefix: str) -> None:
    if not links:
        return
    columns = st.columns(len(links))
    for index, (label, page) in enumerate(links):
        with columns[index]:
            if st.button(label, key=f"{key_prefix}_{index}_{page}"):
                jump_to_page(page)


def render_user_error(
    *,
    title: str,
    exc: Exception,
    fallback: str,
    next_steps: list[str] | None = None,
    links: list[tuple[str, str]] | None = None,
    key_prefix: str = "workspace_error",
) -> None:
    st.error(title)
    st.write(friendly_error_message(exc, fallback=fallback))
    if next_steps:
        st.markdown("**What to do next**")
        for item in next_steps:
            st.markdown(f"- {item}")
    render_navigation_links(links or [], key_prefix=key_prefix)
    with st.expander("Technical details"):
        st.code(repr(exc), language="text")


def render_prerequisite_block(
    *,
    title: str,
    detail: str,
    links: list[tuple[str, str]] | None = None,
    key_prefix: str = "workspace_prerequisite",
) -> None:
    st.markdown(f"**{title}**")
    st.info(detail)
    render_navigation_links(links or [], key_prefix=key_prefix)
