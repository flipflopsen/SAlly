export default function convertDictKeysGrid(dataDict: Record<any, any>) {
    let convertedDataDict: Record<any, any> = {};

    for (let [old_key, data] of Object.entries(dataDict)) {
        // the key is in the form: "0-bus-0_vm_pu"
        // the key is expected to be in the form: "bus 0 vm_pu"
        let splitted = old_key.split("_");
        // splitted = ["0-bus-0", "vm", "pu"]
        let typeId = splitted[0].slice(2).replace("-", " ");
        // typeId = "bus 0"
        let value = splitted.slice(1).join(" ").replace(" ", "_");
        // value = "vm_pu"
        let new_key = typeId + " " + value;
        // new_key = "bus 0 vm_pu"
        convertedDataDict[new_key] = data;
    }

    return convertedDataDict;
}
