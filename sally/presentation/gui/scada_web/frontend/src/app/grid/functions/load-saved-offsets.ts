import State from "../state";
import Vector2D from "../classes/vector-2d";


export default function loadSavedOffsets(state: State,
    networkJsonFileContent: Record<string, any>,
    allDicts:Record<string, any>[]
    ) {

    for (const myDict of allDicts) {
        // load existing element-coordinates
        for (const [elemCimId, elemObj] of Object.entries(myDict)) {
          // overwrite any existing offsets (there are default-offsets from adding a child to a parent)
          if (!(elemCimId in networkJsonFileContent["SAVEDDATA"])){
            console.log(elemCimId, "missing in savedata");
            continue
          }
          elemObj.gridOffsetToParent = new Vector2D(
            networkJsonFileContent["SAVEDDATA"][elemCimId].gridOffsetToParent.x,
            networkJsonFileContent["SAVEDDATA"][elemCimId].gridOffsetToParent.y
          );
          // make sure that the new offset is applied
          elemObj.posChange(new Vector2D(0, 0));
        }
      }
}