/**
 * Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
 * This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
 * conditions defined in the file COPYING, which is part of this source code package.
 */

import * as d3 from "d3";
import {
    DynamicToggleableLayer,
    layer_class_registry,
    LayerSelections,
} from "nodevis/layer_utils";
import {AbstractLink, link_type_class_registry} from "nodevis/link_utils";
import {TopologyNode} from "nodevis/node_types";
import {
    get_custom_node_settings,
    node_type_class_registry,
} from "nodevis/node_utils";
import * as texts from "nodevis/texts";
import {
    d3SelectionDiv,
    d3SelectionG,
    NodevisNode,
    NodevisWorld,
    OverlaysConfig,
} from "nodevis/type_defs";
import {
    RadioGroupOption,
    render_radio_group,
    render_save_delete,
} from "nodevis/utils";
import {Viewport} from "nodevis/viewport";

function render_toggle_panel(
    overlays_config: OverlaysConfig,
    layer_toggled_callback: (layer_id: string, enabled: boolean) => void,
    viewport: Viewport
): void {
    const toggle_panel = viewport
        .get_div_selection()
        .selectAll<HTMLDivElement, null>("div#layout_toggle_panel")
        .data([null])
        .join(enter => enter.append("div").attr("id", "layout_toggle_panel"));
    const options = [
        new RadioGroupOption("all", texts.get("all")),
        new RadioGroupOption("only_problems", texts.get("only_problems")),
        new RadioGroupOption("none", texts.get("none")),
    ];

    // Parent/child does not provide service info
    if (
        overlays_config.available_layers.length > 0 &&
        !overlays_config.available_layers.includes("parent_child")
    )
        toggle_panel
            .selectAll("div.radio_group")
            .data([null])
            .join(enter =>
                enter
                    .insert("div", "table#overlay_configuration")
                    .classed("radio_group", true)
            );
    render_radio_group(
        toggle_panel,
        texts.get("services"),
        "service_visibility",
        options,
        "all",
        (new_option: string) => {
            viewport.get_overlays_config().computation_options.show_services =
                new_option as "all" | "only_problems" | "none";
            // TODO: bad reference usage
            viewport._world_for_layers?.update_data();
        }
    );

    const table = toggle_panel
        .selectAll<HTMLTableElement, null>("table#overlay_configuration")
        .data([null])
        .join("table")
        .attr("id", "overlay_configuration");

    const data: [string, string, (new_value: boolean) => void, boolean][] = [];

    // Only shown on multiple datasources
    if (viewport.get_overlays_config().available_layers.length <= 1) return;

    data.push([
        "merge_nodes",
        texts.get("merge_data"),
        new_value => {
            viewport.get_overlays_config().computation_options.merge_nodes =
                new_value;
            // TODO: bad reference usage
            viewport._world_for_layers?.update_data();
        },
        viewport.get_overlays_config().computation_options.merge_nodes,
    ]);

    overlays_config.available_layers.forEach(layer_id => {
        // TODO: map layer_id to i18n
        data.push([
            layer_id,
            layer_id,
            (new_value: boolean) => layer_toggled_callback(layer_id, new_value),
            overlays_config.overlays[layer_id] &&
                overlays_config.overlays[layer_id].active,
        ]);
    });
    const layer_rows = table
        .selectAll<HTMLTableRowElement, [string, string, () => void]>("tr")
        .data(data, d => d[0])
        .join("tr");

    const option_td = layer_rows
        .selectAll("td.option")
        .data(d => [d])
        .join("td")
        .classed("option", true);

    option_td
        .selectAll<HTMLDivElement, string>(
            "div.nodevis.toggle_switch_container"
        )
        .data(d => [d])
        .join(enter =>
            enter
                .append("div")
                .classed("nodevis toggle_switch_container", true)
                .on("click", (event, d) => {
                    const node = d3.select(event.target);
                    const new_value = !node.classed("on");
                    node.classed("on", new_value);
                    d[2](new_value);
                })
        )
        .classed("on", d => d[3]);

    layer_rows
        .selectAll("td.text")
        .data(d => [d])
        .enter()
        .append("td")
        .classed("text noselect", true)
        .text(d => d[1])
        .style("pointer-events", "all")
        .on("click", (event, d) => {
            const node = d3.select(
                event.target.parentNode.firstChild.firstChild
            );
            const new_value = !node.classed("on");
            node.classed("on", new_value);
            d[2](new_value);
        });
}

export class LayoutTopology {
    _world: NodevisWorld;

    constructor(world: NodevisWorld) {
        this._world = world;
    }

    render_layout(selection: d3SelectionDiv): void {
        this._render_save_delete_layout(selection);
        render_toggle_panel(
            this._world.viewport.get_overlays_config(),
            (layer_id, enabled) => this._toggle_layer(layer_id, enabled),
            this._world.viewport
        );
    }

    _toggle_layer(layer_id: string, enabled: boolean) {
        const layer_config =
            this._world.viewport.get_overlay_layers_config()[layer_id] || {};
        layer_config.active = enabled;
        this._world.viewport.set_overlay_layer_config(layer_id, layer_config);
    }

    _render_save_delete_layout(
        into_selection: d3.Selection<HTMLDivElement, null, any, unknown>
    ): void {
        const buttons: [string, string, string, () => void][] = [
            [
                texts.get("save"),
                "button save_delete save",
                "",
                this._world.save_layout,
            ],
            [
                texts.get("delete_layout"),
                "button save_delete delete",
                "",
                this._world.delete_layout,
            ],
        ];
        render_save_delete(into_selection, buttons);
    }
}

export class GenericNetworkLayer extends DynamicToggleableLayer {
    _ident = "network";
    _name = "network";

    constructor(
        world: NodevisWorld,
        selections: LayerSelections,
        ident: string,
        name: string
    ) {
        super(world, selections);
        this._ident = ident;
        this._name = name;
    }

    override is_dynamic_instance_template(): boolean {
        return true;
    }

    override class_name(): string {
        return "network@";
    }

    override id(): string {
        return this.class_name() + this._ident;
    }

    override name() {
        return this._name;
    }

    override enable_hook() {
        this._world.viewport.try_fetch_data();
    }

    override disable_hook() {
        this._world.viewport.try_fetch_data();
    }
}

layer_class_registry.register(GenericNetworkLayer);

class TopologyCoreEntity extends TopologyNode {
    highlight_connection(traversed_id: Set<string>, start = false) {
        if (traversed_id.has(this.id())) return;
        traversed_id.add(this.id());
        this.selection().classed("white_focus", true);
        if (start)
            this._world.viewport
                .get_nodes_layer()
                .get_links_for_node(this.node.data.id)
                .forEach(link_instance => {
                    if (link_instance instanceof NetworkLink)
                        link_instance.highlight_connection(traversed_id);
                });
    }

    hide_connection(traversed_ids: Set<string>, _start = false) {
        if (traversed_ids.has(this.id())) return;
        traversed_ids.add(this.id());
        this.selection().classed("white_focus", false);
        this._world.viewport
            .get_nodes_layer()
            .get_links_for_node(this.node.data.id)
            .forEach(link_instance => {
                if (link_instance instanceof NetworkLink)
                    link_instance.hide_connection(traversed_ids);
            });
    }

    override render_object() {
        TopologyNode.prototype.render_object.call(this);
    }

    override render_into(selection: d3SelectionG) {
        super.render_into(selection);
        this.selection()
            .on("mouseover.network", () =>
                this.highlight_connection(new Set<string>(), true)
            )
            .on("mouseout.network", () =>
                this.hide_connection(new Set<string>(), true)
            );
    }
    //
    // override _get_node_type_specific_force(
    //     force_name: SimulationForce,
    //     force_options: ForceOptions
    // ): number {
    //     switch (force_name) {
    //         case "center":
    //             return force_options.topo_center_node;
    //         case "charge":
    //             return force_options.topo_grav_node;
    //         default:
    //             return super._get_node_type_specific_force(
    //                 force_name,
    //                 force_options
    //             );
    //     }
    // }
}

class TopologyHost extends TopologyCoreEntity {
    override class_name(): string {
        return "topology_host";
    }

    override update_position() {
        super.update_position();

        this.selection()
            .selectAll("circle.has_warn_services")
            .data(
                this.node.data.type_specific.core.num_services_warn > 0
                    ? [this.node.data.type_specific.core.num_services_warn]
                    : []
            )
            .join("circle")
            .attr("r", this.radius + 6)
            .classed("has_warn_services", true);

        this.selection()
            .selectAll("circle.has_crit_services")
            .data(
                this.node.data.type_specific.core.num_services_crit > 0
                    ? [this.node.data.type_specific.core.num_services_crit]
                    : []
            )
            .join("circle")
            .attr("r", this.radius + 8)
            .classed("has_crit_services", true);
    }

    override get_context_menu_elements() {
        const elements =
            TopologyCoreEntity.prototype.get_context_menu_elements.call(this);

        const custom_settings = get_custom_node_settings(this.node);

        if (custom_settings["show_services"]) {
            elements.push({
                text: texts.get("services_remove_explicit_setting"),
                img: "themes/facelift/images/icon_status.svg",
                on: () => {
                    const node = this._world.viewport.get_node_by_id(this.id());
                    if (!node) return;
                    const custom_settings = get_custom_node_settings(node);
                    delete custom_settings["show_services"];
                    this._world.update_data();
                },
            });
        }

        const current_value = custom_settings["show_services"] || "all";
        let next_option_text = "";
        let next_option_value = "";

        switch (current_value) {
            case "all": {
                next_option_text = texts.get("only_problems");
                next_option_value = "only_problems";
                break;
            }
            case "only_problems": {
                next_option_text = texts.get("none");
                next_option_value = "none";
                break;
            }
            case "none": {
                next_option_text = texts.get("all");
                next_option_value = "all";
                console.log("soso");
                break;
            }
        }
        elements.push({
            text: "Show services: " + next_option_text.toLowerCase(),
            img: "themes/facelift/images/icon_status.svg",
            on: () => {
                const node = this._world.viewport.get_node_by_id(this.id());
                if (!node) return;
                const custom_settings = get_custom_node_settings(node);
                custom_settings["show_services"] = next_option_value;
                this._world.update_data();
            },
        });
        return elements;
    }

    override _get_text(node_id: string): string {
        const node = this._world.viewport.get_node_by_id(node_id);
        if (!node) return "";
        return node.data.name;
    }
}

class TopologyService extends TopologyCoreEntity {
    constructor(world: NodevisWorld, node: NodevisNode) {
        super(world, node);
        this.radius = 4;
        this._provides_external_quickinfo_data = true;
    }
    override class_name(): string {
        return "topology_service";
    }

    override highlight_connection(traversed_id: Set<string>, _start = false) {
        super.highlight_connection(traversed_id, true);
    }

    override update_position() {
        super.update_position();
    }
    override _get_text(node_id: string): string {
        const node = this._world.viewport.get_node_by_id(node_id);
        if (!node) return "";
        return node.data.name;
    }

    override render_object() {
        TopologyNode.prototype.render_object.call(this);
        this.selection()
            .on("mouseover", () => {
                this._show_quickinfo();
                this._highlight_links(true);
            })
            .on("mouseout", () => {
                this._hide_quickinfo();
                this._highlight_links(false);
            });
    }

    _highlight_links(active: boolean) {
        const shown_links = this._world.viewport
            .get_nodes_layer()
            .get_svg_selection()
            .select("g#links")
            .selectAll<SVGPathElement, string>("path");
        const my_id = this.node.data.id;
        shown_links.each((data, idx, nodes) => {
            const tokens = data.split("#@#");
            const source = this._world.viewport.get_node_by_id(tokens[0]);
            const target = this._world.viewport.get_node_by_id(tokens[1]);
            if (source.data.id == my_id || target.data.id == my_id) {
                d3.select(nodes[idx]).attr("stroke-width", active ? "5" : "1");
            }
        });
    }

    override _fetch_external_quickinfo() {
        this._quickinfo_fetch_in_progress = true;
        const [hostname, service] = this._get_hostname_and_service();
        const view_url =
            "view.py?view_name=topology_hover_service&display_options=I&host=" +
            encodeURIComponent(hostname) +
            "&service=" +
            encodeURIComponent(service) +
            "&datasource=" +
            encodeURIComponent(this._world.datasource);
        d3.html(view_url, {credentials: "include"}).then(html =>
            this._got_quickinfo(html)
        );
    }

    override get_context_menu_elements() {
        const elements =
            TopologyCoreEntity.prototype.get_context_menu_elements.call(this);
        const [hostname, service] = this._get_hostname_and_service();
        elements[0] = {
            text: "Details of Service",
            href:
                "view.py?host=" +
                encodeURIComponent(hostname) +
                "&view_name=service&service=" +
                encodeURIComponent(service),
            img: "themes/facelift/images/icon_status.svg",
        };
        return elements;
    }

    _get_hostname_and_service() {
        return [
            this.node.data.type_specific.core.hostname,
            this.node.data.type_specific.core.service,
        ];
    }
}

class TopologyUnknown extends TopologyNode {
    override class_name(): string {
        return "topology_unknown";
    }

    override render_object() {
        super.render_object();
        this.selection()
            .selectAll("image.unknown")
            .data([this.id()])
            .enter()
            .insert("svg:image", "image")
            .classed("unknown", true)
            .attr("xlink:href", "themes/facelift/images/icon_alert_unreach.png")
            .attr("x", -15)
            .attr("y", -15)
            .attr("width", 30)
            .attr("height", 30);
    }
}

node_type_class_registry.register(TopologyUnknown);
node_type_class_registry.register(TopologyHost);
node_type_class_registry.register(TopologyService);

class NetworkLink extends AbstractLink {
    highlight_connection(traversed_ids: Set<string>) {
        if (traversed_ids.has(this.id())) return;
        traversed_ids.add(this.id());
        this.selection().classed("white_focus", true);
        [
            this._link_data.source.data.id,
            this._link_data.target.data.id,
        ].forEach(id => {
            const gui_node = this._world.viewport
                .get_nodes_layer()
                .get_node_by_id(id) as TopologyCoreEntity;
            gui_node.highlight_connection(traversed_ids);
        });
    }

    hide_connection(traversed_ids: Set<string>) {
        if (traversed_ids.has(this.id())) return;
        traversed_ids.add(this.id());
        this.selection().classed("white_focus", false);
        [
            this._link_data.source.data.id,
            this._link_data.target.data.id,
        ].forEach(id => {
            const gui_node = this._world.viewport
                .get_nodes_layer()
                .get_node_by_id(id) as TopologyCoreEntity;
            gui_node.hide_connection(traversed_ids);
        });
    }

    override render_into(selection: d3SelectionG) {
        super.render_into(selection);
        this.selection()
            .style("pointer-events", "all")
            .on("mouseover", event => {
                this.highlight_connection(new Set<string>());
                this._show_link_info(
                    event,
                    this._link_data.config.link_info
                        ? [this._link_data.config.link_info]
                        : []
                );
            })
            .on("mouseout", event => {
                this.hide_connection(new Set<string>());
                this._show_link_info(event, []);
            })
            .on("mousemove", event => {
                this._show_link_info(
                    event,
                    this._link_data.config.link_info
                        ? [this._link_data.config.link_info]
                        : []
                );
            });
        if (this._link_data.config.css) {
            this.selection().attr("class", this._link_data.config.css);
        }
    }

    _show_link_info(event: {layerX: number; layerY: number}, info: string[]) {
        this._world.viewport
            .get_nodes_layer()
            .get_div_selection()
            .selectAll("label.link_info")
            .data(info)
            .join("label")
            .classed("link_info", true)
            .text(d => d)
            .style("position", "absolute")
            .style("left", event.layerX + 20 + "px")
            .style("top", event.layerY - 10 + "px");
    }
}

export class HostServiceLink extends NetworkLink {
    override class_name(): string {
        return "host2service";
    }

    override _color(): string {
        return "grey";
    }

    // override _get_link_type_specific_force(
    //     force_name: SimulationForce,
    //     force_options: ForceOptions
    // ): number {
    //     switch (force_name) {
    //         case "link_distance":
    //             return force_options.topo_link_node_if;
    //         case "link_strength":
    //             return force_options.topo_str_node_if;
    //         default:
    //             return super._get_link_type_specific_force(
    //                 force_name,
    //                 force_options
    //             );
    //     }
    // }
}

export class HostHostLink extends NetworkLink {
    override class_name() {
        return "host2host";
    }

    override _color(): string {
        return "grey";
    }

    // _get_link_type_specific_force(
    //     force_name: SimulationForce,
    //     force_options: ForceOptions
    // ): number {
    //     switch (force_name) {
    //         case "link_distance":
    //             return force_options.topo_link_node_node;
    //         case "link_strength":
    //             return force_options.topo_str_node_node;
    //         default:
    //             return super._get_link_type_specific_force(
    //                 force_name,
    //                 force_options
    //             );
    //     }
    // }
}

export class ServiceServiceLink extends NetworkLink {
    override class_name() {
        return "service2service";
    }

    override _color(): string {
        return "darkgrey";
    }

    // _get_link_type_specific_force(
    //     force_name: SimulationForce,
    //     force_options: ForceOptions
    // ): number {
    //     switch (force_name) {
    //         case "link_distance":
    //             return force_options.topo_link_if_if;
    //         case "link_strength":
    //             return force_options.topo_str_if_if;
    //         default:
    //             return super._get_link_type_specific_force(
    //                 force_name,
    //                 force_options
    //             );
    //     }
    // }
}

link_type_class_registry.register(HostServiceLink);
link_type_class_registry.register(HostHostLink);
link_type_class_registry.register(ServiceServiceLink);
