from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select

from aws_local_audit.db import session_scope
from aws_local_audit.models import Framework, OrganizationFrameworkBinding
from aws_local_audit.services.workbench import WorkbenchService
from aws_local_audit.services.security import ConfluenceConnectionService
from ui_support import jump_to_page, render_prerequisite_block, render_user_error


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hero"><h1 style="margin:0;">{title}</h1><p style="margin:0.35rem 0 0 0;">{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def render_portfolio_center() -> None:
    _hero(
        "Portfolio",
        "Create organizations, products, and framework bindings without dealing with flavors or hidden setup dependencies.",
    )
    st.markdown(
        '<div class="section-note">This page defines who is in scope and which products are covered. Control implementations, SoA decisions, and evidence plans are managed in Control Framework Studio once the scope exists.</div>',
        unsafe_allow_html=True,
    )
    with session_scope() as session:
        service = WorkbenchService(session)
        organizations = service.list_organizations()
        products = service.list_products()
        bindings = session.scalars(
            select(OrganizationFrameworkBinding).order_by(OrganizationFrameworkBinding.updated_at.desc())
        ).all()

        tabs = st.tabs(["Organizations", "Products", "Framework Bindings"])

        with tabs[0]:
            left, right = st.columns([0.9, 1.1])
            with left:
                with st.form("portfolio_org_form"):
                    name = st.text_input("Organization name")
                    code = st.text_input("Organization code")
                    description = st.text_area("Description", height=100)
                    save = st.form_submit_button("Save organization", type="primary")
                if save and name:
                    try:
                        organization = service.create_organization(name=name, code=code or None, description=description)
                        st.success(f"Organization ready: {organization.code}")
                    except Exception as exc:
                        render_user_error(
                            title="Could not save the organization",
                            exc=exc,
                            fallback="The organization could not be saved right now.",
                            key_prefix="portfolio_org_error",
                        )
            with right:
                if organizations:
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {"Code": item.code, "Name": item.name, "Status": item.status}
                                for item in organizations
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    render_prerequisite_block(
                        title="No organizations yet",
                        detail="Create your first organization here so products and controls have a business owner and a reporting boundary.",
                    )

        with tabs[1]:
            if not organizations:
                render_prerequisite_block(
                    title="Create an organization first",
                    detail="Products are always attached to an organization.",
                    links=[("Open Organizations", "Portfolio")],
                    key_prefix="portfolio_missing_org",
                )
            else:
                left, right = st.columns([0.9, 1.1])
                with left:
                    with st.form("portfolio_product_form"):
                        organization_code = st.selectbox("Organization", [item.code for item in organizations])
                        name = st.text_input("Product name")
                        code = st.text_input("Product code")
                        product_type = st.selectbox("Product type", ["service", "platform", "application", "component"])
                        deployment_model = st.selectbox(
                            "Deployment model",
                            ["saas", "managed", "hybrid", "self-hosted"],
                        )
                        owner = st.text_input("Owner")
                        save = st.form_submit_button("Save product", type="primary")
                    if save and name:
                        try:
                            product = service.create_product(
                                organization_code=organization_code,
                                name=name,
                                code=code or None,
                                product_type=product_type,
                                deployment_model=deployment_model,
                                owner=owner,
                            )
                            st.success(f"Product ready: {product.code}")
                        except Exception as exc:
                            render_user_error(
                                title="Could not save the product",
                                exc=exc,
                                fallback="The product could not be saved right now.",
                                key_prefix="portfolio_product_error",
                            )
                with right:
                    if products:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Organization": item.organization.code,
                                        "Product": item.code,
                                        "Name": item.name,
                                        "Type": item.product_type,
                                        "Deployment": item.deployment_model,
                                    }
                                    for item in products
                                ]
                            ),
                            width="stretch",
                            hide_index=True,
                        )
                        if st.button("Open Control Framework Studio for product work", key="portfolio_open_control_studio"):
                            jump_to_page("Control Framework Studio")
                    else:
                        st.info("No products have been created yet.")

        with tabs[2]:
            framework_codes = [item.code for item in session.scalars(select(Framework).order_by(Framework.code)).all()]
            connection_names = [item.name for item in ConfluenceConnectionService(session).list_connections()]
            if not organizations or not products:
                render_prerequisite_block(
                    title="Create an organization and a product first",
                    detail="A framework binding becomes useful once you already know which organization and product will use it.",
                    links=[("Open Products", "Portfolio")],
                    key_prefix="portfolio_bindings_missing_scope",
                )
            else:
                if not framework_codes:
                    render_prerequisite_block(
                        title="Seed frameworks first",
                        detail="You need at least one framework before creating a binding.",
                        links=[("Open Guided Setup", "Wizards")],
                        key_prefix="portfolio_bindings_missing_frameworks",
                    )
                else:
                    with st.form("portfolio_binding_form"):
                        organization_code = st.selectbox("Organization", [item.code for item in organizations], key="portfolio_binding_org")
                        product_options = [item.code for item in products if item.organization.code == organization_code]
                        product_code = st.selectbox("Product", product_options or [""], key="portfolio_binding_product")
                        framework_code = st.selectbox("Framework", framework_codes, key="portfolio_binding_framework")
                        aws_profile = st.text_input(
                            "AWS profile",
                            help="Optional for now. Add it later when this scope is ready for live AWS evidence collection.",
                        )
                        aws_region = st.text_input("AWS region", value="eu-west-1")
                        confluence_connection = st.selectbox("Confluence connection", [""] + connection_names)
                        save = st.form_submit_button("Save framework binding", type="primary")
                    if save and organization_code and framework_code and product_code:
                            try:
                                binding = service.bind_framework(
                                    organization_code=organization_code,
                                    framework_code=framework_code,
                                    aws_profile=aws_profile.strip(),
                                    aws_region=aws_region,
                                    confluence_connection_name=confluence_connection or None,
                                )
                                if aws_profile.strip():
                                    st.success(f"Framework binding ready: {binding.binding_code}")
                                else:
                                    st.success(
                                        f"Framework binding ready: {binding.binding_code}. You can add the AWS profile later when you start live evidence collection."
                                    )
                            except Exception as exc:
                                render_user_error(
                                    title="Could not save the framework binding",
                                    exc=exc,
                                    fallback="The framework binding could not be saved right now.",
                                    key_prefix="portfolio_binding_error",
                                )
                    elif save and not product_code:
                        render_prerequisite_block(
                            title="Choose a product first",
                            detail="A framework binding should be attached to a concrete product scope.",
                            key_prefix="portfolio_binding_missing_product",
                        )

            if bindings:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Binding": item.binding_code,
                                "Organization": item.organization.code,
                                "Framework": item.framework.code,
                                "AWS Profile": item.aws_profile,
                                "Region": item.aws_region,
                            }
                            for item in bindings
                        ]
                    ),
                    width="stretch",
                    hide_index=True,
                )
