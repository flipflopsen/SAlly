import State from "../state";
import Vector2D from "../classes/vector-2d";
import * as SETTINGS from "../settings";

export default function sAAA(state: State, allDicts:Record<string, any>[]) {
    // set a start by fixing all external-grid elements
    let parentElementsDicts = [state.extGridDict, state.switchDict];
    parentElementsDicts.forEach((elemDict) => {
      for (const [key, obj] of Object.entries(elemDict)) {
        obj.posChange(new Vector2D(
          SETTINGS.MAINGRIDSTARTGRIDCOOR.x / (SETTINGS.MINELEMENTDISTANCE / SETTINGS.ELEMENTSIZE),
          SETTINGS.MAINGRIDSTARTGRIDCOOR.y / (SETTINGS.MINELEMENTDISTANCE / SETTINGS.ELEMENTSIZE)
        ));
      }
    });
    
    // arrange the elements with S-AAA
    // --> call the reserveSpace-function for each node iterativly
    let numChanges: number;
    let change: Vector2D;
    for (let i = 0; i < SETTINGS.MAXITERATIONS; i++) {
      numChanges = 0;
      for (const myDict of allDicts) {
        for (const [elemCimId, elemObj] of Object.entries(myDict)) {
          change = elemObj.reserveSpace();
          if ((change.x != 0) || (change.y != 0)) {
            numChanges++;
          }
        }
      }
      if (numChanges == 0) {
        // algorithm reached a steady state, aboard!
        if(SETTINGS.SHOWDEBUGGINGINFO){   
          console.log("S-AAA finished after", i, "iterations");
        }
        break;
      }
    }
}