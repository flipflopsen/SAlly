export interface Base {
    cim_id: string,
    name: string,
    id: number
}

export interface BaseNoName {
    cim_id: string,
    name: null,
    id: number
}

export interface BusElement extends Base {
    vn_kv: number
}

export interface LoadElement extends Base {
    bus: number,
    p_mw: number,
    q_mvar: number,
    sn_mva: null
}

export interface SgenElement extends Base {
    bus: number,
    p_mw: number,
    q_mvar: number,
    sn_mva: number,
    min_p_mw: number,
    max_p_mw: number
}

export interface SwitchElement extends BaseNoName{
    bus: number
}

export interface ExtGridElement extends Base {
    bus: number
}

export interface LineElement extends BaseNoName {
    from_bus: number,
    to_bus: number,
    max_i_ka: number
}

export interface TrafoElement extends Base {
    hv_bus: number,
    lv_bus: number,
    vn_hv_kv: number,
    vn_lv_kv: number,
    tap_side: string,
    sn_mva: number
}
