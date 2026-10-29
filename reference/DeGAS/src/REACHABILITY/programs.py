def get_program(name):
    if name == 'bouncing_ball':
        x = '''
        array[36] H;

        /* Initial state */
        currH = gauss(9., 1.);   
        mode = -1.;
        currV = 0.;

        bounced = -1.;
        valid = -1.;
        count = 0.;

        dt = 0.08;            

        for i in range(35) {
            /* Save current state */
            H[i] = currH;

            /* Continuous dynamics */

            if mode < 0 {
                /* falling down */
                temp = -9.8 * dt;
                newV = currV + temp + gauss(0., 0.1);
            } else {
                /* going up */
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

            /* Mode switching */
            if mode < 0 {
                if currH <= 0. {
                    mode = 1;
                    bounced = 1.;
                } else {
                    skip;
                } end if;
            } else {
                if currH > 0. {
                    mode = -1;
                    if bounced > 0. {
                        valid = count;
                    } else {
                        skip;
                    } end if;
                } else {
                    skip;
                } end if;
            } end if;
            count = count + 1.;
        } end for;

        /* Save final state */
        H[35] = currH;
        '''
        params = {'R':  7., 'C':200.}
        t = 35
        traj_var = 'H'

    elif name == 'gearbox':
        x = '''
        array[21] v;

        w = 0;             
        gear = 1;           
        currV = 5;         

        for i in range(21) {

            v[i] = currV;          

            if gear > 0.5 {
                newV = 1.078*currV + 0.1*gauss(5., 1.);
            } else {
                newV = currV*currV;
                newV = 0.00005*newV;
                newV = currV - newV + gauss(0, 1.);
            } end if;

            currV = newV;         

            if gear > 0.5 {
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
                if w < 0.05 {
                    gear = nxt;             
                } else {
                    skip;
                } end if;
            } end if;

            w = w - 0.1;

            v[i] = v[i] + gauss(0., 0.5);

        } end for;
               '''
        params = {'s1':10., 's2':20.}
        t = 20
        traj_var = 'v'

    elif name == 'thermostat':
        x = '''
        array[26] T;
        array[26] M; 

        /* Initial state */
        currT = gauss(30., 1.);   
        isOn = 1;                 

        dt = 0.1;            

        for i in range(25) {

            /* Save current state */
            T[i] = currT;
            M[i] = isOn;

            /* Continuous dynamics */
            if isOn > 0 {
                /* Cooling: dT/dt = -T */
                temp = currT * dt;
                newT = currT - temp + gauss(0., 0.1);
            } else {
                /* Heating: dT/dt = -(T-30) */
                temp = currT * dt;
                newT = currT - temp ;
                temp = 30. * dt;
                newT = newT + temp + gauss(0., 0.1);
            } end if;

            currT = newT;

            /* Mode switching */
            if isOn > 0 {
                if currT < _tOff {
                    isOn = -1;
                } else {
                    skip;
                } end if;
            } else {
                if currT >= _tOn {
                    isOn = 1;
                } else {
                    skip;
                } end if;
            } end if;

        } end for;

        /* Save final state */
        T[25] = currT;
        M[25] = isOn;
        '''
        params = {'tOff':  16.5, 'tOn':22.}
        t = 25
        traj_var = 'T'
    else:
        raise ValueError(f"Unknown program name: {name}")

    return x, params, t, traj_var