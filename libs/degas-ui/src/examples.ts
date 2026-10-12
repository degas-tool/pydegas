export interface Example {
  label: string;
  program: string;
  initial_params: Record<string, number>;
  loss_function: string;
  loss_kwargs: Record<string, unknown>;
  n_steps: number;
  optimizer: string;
  optimizer_kwargs: Record<string, unknown>;
  pruning?: 'classic' | 'ranking' | 'kmeans';
}

export const EXAMPLES: Example[] = [
  {
    label: "Thermostat",
    program: `/* Thermostat — Chaudhuri & Solar-Lezama (2010)
 * Learn the on/off temperature thresholds _tOn and _tOff.
 */

array[31] T;

currT = 16;
isOn = -1;

for i in range(31) {

    T[i] = currT;

    if isOn > 0 {
        newT = 0.99*currT + 0.5 + gauss(0., 0.1);
    } else {
        newT = 0.99*currT + gauss(0., 0.1);
    } end if;

    currT = newT;

    if isOn > 0 {
        if newT > _tOff {
            isOn = -1;
        } else {
            skip;
        } end if;
    } else {
        if newT < _tOn {
            isOn = 1;
        } else {
            skip;
        } end if;
    } end if;
    prune(10);

} end for;

T[30] = currT;

for i in range(30) {
    T[i] = T[i] + gauss(0, 1);
} end for;`,
    initial_params: { tOff: 22.0, tOn: 15.0 },
    loss_function: "signal_error",
    loss_kwargs: { target: 18.0, time_steps: 31 },
    n_steps: 100,
    optimizer: "Adam",
    optimizer_kwargs: { lr: 0.2 },
    pruning: "kmeans",
  },
  {
    label: "Gearbox",
    program: `/* Gearbox — learn optimal gear-shift velocity thresholds.
 * _s1: velocity threshold for 1st→2nd gear shift
 * _s2: velocity threshold for 2nd→3rd gear shift
 */

array[21] v;

w = 0;
gear = 1;
currV = 5;

for i in range(21) {

    v[i] = currV;

    if gear > 0.8 {
        newV = 1.078*currV;
        temp = 0.1*gauss(5., 1.);
        newV = newV + temp;
    } else {
        newV = currV*currV;
        newV = 0.00005*newV;
        newV = currV - newV + gauss(0, 1.);
    } end if;

    currV = newV;

    if gear > 0. {
        if gear < 1.5 {
            if newV > _s1 {
                nxt = gear + 1;
                gear = 0;
                w = 0.3;
            } else {
                skip;
            } end if;
        } else {
            if gear < 2.5 {
                if newV > _s2 {
                    nxt = gear + 1;
                    gear = 0;
                    w = 0.3;
                } else {
                    skip;
                } end if;
            } else {
                skip;
            } end if;
        } end if;
    } else {
        if w < 0.1 {
            gear = nxt;
        } else {
            skip;
        } end if;
    } end if;

    w = w - 0.1;
    v[i] = v[i] + gauss(0., 0.5);

    prune(10);

} end for;`,
    initial_params: { s1: 8.0, s2: 12.0 },
    loss_function: "signal_error",
    loss_kwargs: { target: 15.0, time_steps: 21 },
    n_steps: 200,
    optimizer: "Adam",
    optimizer_kwargs: { lr: 0.3 },
    pruning: "kmeans",
  },
  {
    label: "PID",
    program: `/* PID — Chaudhuri & Solar-Lezama (2010) Case Study 3.
 * Tune the proportional/derivative/integral gains _s0, _s1, _s2
 * so the controller drives the angle to target = 3.14.
 */

array[51] ang;

v = 0;
currAng = 0.5;
id = 0;
oldv = 0;

for i in range(51) {

    ang[i] = currAng;

    d = 3.14 - currAng;
    torq = _s0*d + _s1*v + _s2*id;
    id = 0.9*id + 0.1*d;
    oldv = v;

    v = v + 0.01*torq + gauss(0, 0.25);
    currAng = currAng + 0.05*v + 0.05*oldv + gauss(0., 0.25);
    prune(10);

} end for;

ang[50] = currAng;`,
    initial_params: { s0: 46.0, s1: -23.0, s2: 0.0 },
    loss_function: "signal_error",
    loss_kwargs: { target: 3.14, time_steps: 51 },
    n_steps: 500,
    optimizer: "Adam",
    optimizer_kwargs: { lr: 0.2 },
    pruning: "kmeans",
  },
  {
    label: "BouncingBall",
    program: `/* Bouncing ball — Chaudhuri & Solar-Lezama (2010).
 * Recover the spring/damping parameters _R and _C from an observed
 * height trajectory. 
 */

array[36] H;

currH = gauss(9., 1.);
mode = -1.;
currV = 0.;

dt = 0.08;

for i in range(35) {
    H[i] = currH;

    if mode < 0 {
        temp = -9.8 * dt;
        newV = currV + temp + gauss(0., 0.1);
    } else {
        temp = -9.8 * dt;
        spring = _R*currV;
        temp2 = _C*currH;
        spring = spring + temp2;
        spring = spring * dt;
        spring = 0.14 * spring;
        newV = currV + temp - spring + gauss(0., 0.1);
    } end if;

    currV = newV;

    temp = currV * dt;
    newH = currH + temp + gauss(0., 0.1);

    currH = newH;

    if mode < 0 {
        if currH <= 0. {
            mode = 1;
        } else {
            skip;
        } end if;
    } else {
        if currH > 0. {
            mode = -1;
        } else {
            skip;
        } end if;
    } end if;
    prune(10);
} end for;

H[35] = currH;`,
    initial_params: { R: -1.0, C: 450.0 },
    loss_function: "l2_distance",
    loss_kwargs: {},
    n_steps: 100,
    optimizer: "Adam",
    optimizer_kwargs: { lr: 0.8 },
    pruning: "kmeans",
  },
];
