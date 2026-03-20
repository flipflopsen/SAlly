let idCnt = 0;
let wireIdCnt = 0;

// this function makes sure that every object has an easy to read id for debugging purposes
export default function giveID(descriptor: string) {
  if(descriptor === "wire"){
    return wireIdCnt++;
  }
  return idCnt++;
}
