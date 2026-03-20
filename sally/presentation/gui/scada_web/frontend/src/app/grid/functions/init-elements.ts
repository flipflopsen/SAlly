import State from "../state";
import initStructuralElement from "./init-structural-element";
import Bus from "../classes/bus";
import ExtGrid from "../classes/ext-grid";
import Generator from "../classes/generator";
import Load from "../classes/load";
import Trafo from "../classes/trafo";
import Vector2D from "../classes/vector-2d";
import * as SETTINGS from "../settings";
import Switch from "../classes/switch";

export default function initElements(
    networkConfigFileCategoryName: string,
    classType: typeof Bus | typeof ExtGrid | typeof Generator | typeof Load | typeof Trafo,
    classDict: Record<string, Bus | ExtGrid | Generator | Load | Trafo | Switch>,
    state: State) {

    let id_cnt = 0;
    if (networkConfigFileCategoryName in state.networkConfigFile!){
        Object.keys(state.networkConfigFile![networkConfigFileCategoryName]).forEach((key: any) => {
            classDict[key] = initStructuralElement(state, classType, key, state.networkConfigFile![networkConfigFileCategoryName][key], new Vector2D(0, 0));
            classDict[key].id = parseInt(key.split(" ")[1]); // "load 1" --> 1
            id_cnt++;
        });
    }

    if(SETTINGS.SHOWDEBUGGINGINFO){   
        console.log("added " + id_cnt + " elements of type " + networkConfigFileCategoryName);
    }
}
