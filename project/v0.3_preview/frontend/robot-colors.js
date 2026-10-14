// One palette shared by the 2D map, 3D robots, route lines and status cards.
const palette=['#43adf5','#ffb154','#6bcea7','#b195f0','#ef8295','#f0cd60',
               '#55d6dd','#f08ab6','#b6d873','#9facff','#7bc9ba','#e69b7a'];
export const robotColor=id=>palette[(id-1)%palette.length];
