function matlab_script(name, escritura, Fs, n_channels, path, output)
    close all
    clc

    %Si son archis MAT
    filename = sprintf([name '.mat']);

    %Para usar con DAT
    file = fullfile('C:\Users\Becario 4\Documents\TDMS2MAT\salida' , filename); %Leer archivo en SCHUSTER-PC

    %Versión *.MAT
    load(file);
    u = data;


    %VALORES PASADOS POR SERGIO.
    Da = 2*762/1000;    %[m] Diam Cilindro
    da = 2*350/1000;    %[m] Diam Vastago
    Dc = Da;            %[m] Diam Cilindro
    dc = 2*101.6/1000;  %[m] Diam CaÃ±eria
    A_a = pi*(Da^2 - da^2)/4;   %Ã?rea abrir
    A_c = pi*(Dc^2 - dc^2)/4;   %Ã?rea cerrar

    Fza_Hid = (u(:,7)*A_c - u(:,6)*A_a)*100/5;
    %Pos_Alabes = u(:, 3);

    %vector tiempo
    t=0:1/10:(length(Fza_Hid)/10)-(1/10);
    t = t';

    %conteo de ciclos rainflow

    [c, rm, rmr, rmm, idx] = rainflow(Fza_Hid);

    t_t = t(idx);
    Fza_Hid_t = Fza_Hid(idx);

    dP = u(:, 7)-u(:, 6); %delta presiÃ³n
    lim_inf_max = -0.45*ones(length(t),1);  %lÃ­mites para conteo
    lim_inf_min = -0.5*ones(length(t),1);   %lÃ­mites para conteo
    lim_sup_max = 0.5*ones(length(t),1);  %lÃ­mites para conteo
    lim_sup_min = 0.45*ones(length(t),1);   %lÃ­mites para conteo

    Mov_rel = u(:, 8) - u(1, 8);






    %%
    [c, rm, rmr, rmm, idx] = rainflow(Fza_Hid);

    rmr1 = rmr(rmr>=50);
    rm1=rm((length(rmr)-length(rmr1)+1):end, :);
    rmr = rmr1;
    rm = rm1;


    [cFs, rmFs, rmrFs, rmmFs, idxFs] = rainflow(Fza_Hid, Fs);
    To = array2table(cFs,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]'});



    %%
    %CONTEO DE CICLOS CON FILTRO DE AVANCE DE FISURA.
    %DK = 14

    %ObteniciÃ³n de curva 
    K = [65.12307378 57.01521195 42.83250569 27.55061352 14.93805445 7.055368592 3.505949635 2.470266626 2.331041354]';
    F = [1782 1560 1337 1114 891 668 446 223 100];
    pp = spline(F, K);

    f = 0 : 0.1 : 1800;
    k_p = ppval(pp, f);
    figure;
    plot(f, k_p, F, K, '*r');
    title('Curva factor K');
    xlabel('Fuerza [kN]');
    ylabel('Factor K [MPa x m^{1/2}]');


    cFs_filter_dK1 = [];
    cFs_filter_dK2 = [];
    cFs_filter_dK3 = [];
    dK_1 = 14;      %umbral para consideraciÃ³n de ciclos.
    dK_2 = 10.5;    %umbral para consideraciÃ³n de ciclos.
    dK_3 = 7;       %umbral para consideraciÃ³n de ciclos.

    m = length(cFs);
    j_dK1 = 0; j_dK2 = 0; j_dK3 = 0;
    for i = 1 : m  
        f_i = cFs(i, 3) - cFs(i, 2)/2;
        f_s = cFs(i, 3) + cFs(i, 2)/2;
        if f_i < 0
            k_i = 0;
        else
            k_i = ppval(pp, f_i);
        end
        if f_s < 0
            k_s = 0;
        else
            k_s = ppval(pp, f_s);
        end
    %     k_temp = spline(F, K, [cFs(i, 3) - cFs(i, 2)/2 cFs(i, 3) + cFs(i, 2)/2]);
        dK = k_s  - k_i;
    %     dK = k_temp(2) - k_temp(1);
        if dK >= dK_1
            j_dK1 = j_dK1 + 1;
            cFs_filter_dK1(j_dK1,:) = [cFs(i, :) dK];             
            j_dK2 = j_dK2 + 1;
            cFs_filter_dK2(j_dK2,:) = [cFs(i, :) dK];        
            j_dK3 = j_dK3 + 1;
            cFs_filter_dK3(j_dK3,:) = [cFs(i, :) dK];        
        elseif dK >= dK_2
            j_dK3 = j_dK3 + 1;
            cFs_filter_dK3(j_dK3,:) = [cFs(i, :) dK];
            j_dK2 = j_dK2 + 1;  
            cFs_filter_dK2(j_dK2,:) = [cFs(i, :) dK];        
        elseif dK >= dK_3
            j_dK3 = j_dK3 + 1;
            cFs_filter_dK3(j_dK3,:) = [cFs(i, :) dK];    
        end
    end
    if j_dK1 == 0
        cFs_filter_dK1(j_dK1 + 1, :) = zeros(1,length(cFs(1, :))+1);
    end
    if j_dK2 == 0
        cFs_filter_dK2(j_dK2 + 1, :) = zeros(1,length(cFs(1, :))+1);
    end
    if j_dK3 == 0
        cFs_filter_dK3(j_dK3 + 1, :) = zeros(1,length(cFs(1, :))+1);
    end
    %escritura tabla completa
    if escritura
        filename = sprintf([name '.xlsx']);

        file = fullfile(output , filename);
        writetable(To, file, 'Sheet', 'Conteo Rainflow', 'Range', 'A1');


        %escritura tabla valores de dK >= 14
        T = array2table(cFs_filter_dK1,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'});
        writetable(T, file, 'Sheet', 'delta K = 14', 'Range', 'A1');

        %escritura tabla valores de dK >= 10.5
        T = array2table(cFs_filter_dK2,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'});
        writetable(T, file, 'Sheet', 'delta K = 10.5', 'Range', 'A1');

        %escritura tabla valores de dK >= 7
        T = array2table(cFs_filter_dK3,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'})
        writetable(T, file, 'Sheet', 'delta K = 7', 'Range', 'A1');
    end

    close all
    X = [name, ' - Cantidad de Movimientos: ', num2str(Mov_rel(end))];
    disp(X) 
    disp("FINALIZADO")
end