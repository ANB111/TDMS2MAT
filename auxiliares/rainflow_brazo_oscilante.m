for ii = 1:3    
    close all
%     clear all
%     clc
    kk=ii;
    vars = who;
    keep = {'ii'};
    aBorrar = setdiff(vars, keep);
    clear(aBorrar{:});
    if ii == 1
        primerPasada = true; %variable que se usa para que la primer pasada no lea el archivo que contiene el numero de arranques y paradas.
    else
        primerPasada = false;
    end
    escritura = false;
    n_channels = 16;   %Dependiendo la etapa de adquisicion ajustar este valor al numero de canales que se adquieren del PLC.
    name = ['25.9.' num2str(ii) '-u05'];
    % filename = s2printf('Ensayos_U05_27-12-22.DAT');

    % % Si son archivos DAT
    % filename = sprintf([name '.dat']);

    %Si son archis MAT
    filename = sprintf([name '.mat']);

    % file = fullfile('C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia hasta PRIMERA Verificaci√≥n (TDMS)\archivos dat' , filename);
    % file = fullfile('C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia hasta SEGUNDA Verificaci√≥n (TDMS)\Archivos DAT' , filename);
    % file = fullfile('\\schuster-pc\PR178 - Instrumentaci√≥n cubo U05\Mediciones\Datos CHY\U05 - Medici√≥n Semanal Variables\Archivos DAT' , filename);
    % file = fullfile('\\posadas-pc\labse\PR178 - Instrumentaci√≥n cubo U05\Mediciones\Datos CHY\U05 - Medici√≥n Semanal Variables\Archivos DAT' , filename);
    % 
    % %Para usar con MAT
    % file = fullfile('\\schuster-pc\Central HidroelÈctrica Yacyret· (CHY)\PR178  - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\Mediciones Semanales\Modo Potencia Sin Influencia hasta SEGUNDA VerificaciÛn [16.3.2023]' , filename); %Leer archivo en SCHUSTER-PC
    % 
    % Para usar con DAT
    % file = fullfile('\\posadas-pc\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT-MAT' , filename); %Leer archivo en SCHUSTER-PC

    % file = fullfile('C:\DATOS\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT' , filename); %Leer archivo en carpeta local de nextcloud
    % -->file = fullfile('\\posadas-pc\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT' , filename);
    % file = fullfile('C:\Users\Usuario\Downloads' , filename);

    %LOCAL
    file = fullfile('D:\Nextcloud\Proyectos LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT-MAT' , filename); %Leer archivo en SCHUSTER-PC
    % file = fullfile('C:\DATOS\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT' , filename); %Leer archivo en SCHUSTER-PC

    %-------------------USAR DESDE AFUERA DE SCHUSTER-PC-------------------%
    % file = fullfile('\\schuster-pc\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT' , filename); %Leer archivo en SCHUSTER-PC

    %-------------------USAR EN SCHUSTER-PC-------------------%
    % file = fullfile('D:\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Archivos DAT' , filename); %Leer archivo en SCHUSTER-PC
    % 
    % %VersiÛn *.DAT
    % fileID = fopen(file);
    % u = fread(fileID, [1, inf] , 'double');
    % fclose(fileID);
    % u=u';
    % % u=u(2:end);
    % u = reshape(u, [length(u)/n_channels, n_channels]);


    %VersiÛn *.MAT
    load(file);
    % load('C:\Users\Usuario\Downloads\PRUEBA\25.2.13-u05.mat')
    u = data;

    Fs = 10; %Hz

    %{
    Los datos de "u" se encuentran separados en columnas
     de la siguiente forma:
    1-  Potencia (MW)
    2-  Paletas (%)
    3-  √?labes (%)
    4-  Pres_Abrir_Pal(bar)
    5-  Pres_Cerrar_Pal(bar)
    6-  Pres_Abrir_Alab(bar)
    7-  Pres_Cerrar_Alab(bar)
    8-  Cont_Potencia_Sin_Inf
    9-  Conta_Potencia_Con_Inf
    10- Contador_Apertura
    11- Contador_Velocidad
    12- ActualHead

    Nuevos archivos semanales:
    1- Potencia (MW)
    2- Paletas (%)
    3- √?labes (%)
    4- Pres_Abrir_Pal(bar)
    5- Pres_Cerr_Pal(bar)
    6- Pres_Abrir_Alab(bar)
    7- Pres_Cerr_Alab(bar)
    8- Cont_Potencia(c)
    9- Consigna_Pal(%)
    10- Consigna_Pot(MW)
    11- Consigna_Alab(%)
    12- Salto_Reg(m)
    13- Velocidad(%)
    14- Frecuencia(Hz)
    15- ModoPotCon

    Nuevos archivos semanales luego de primera parada de revision:
    1- Potencia (MW)
    2- Paletas (%)
    3- √?labes (%)
    4- Pres_Abrir_Pal(bar)
    5- Pres_Cerr_Pal(bar)
    6- Pres_Abrir_Alab(bar)
    7- Pres_Cerr_Alab(bar)
    8- Cont_Potencia(c)
    9- Consigna_Pal(%)
    10- Consigna_Pot(MW)
    11- Consigna_Alab(%)
    12- Salto_Reg(m)
    13- Velocidad(%)
    14- Frecuencia(Hz)
    15- ModoPotCon
    16- FaseDiv2

    %}

    %VALORES PASADOS POR SERGIO.
    Da = 2*762/1000;    %[m] Diam Cilindro
    da = 2*350/1000;    %[m] Diam Vastago
    Dc = Da;            %[m] Diam Cilindro
    dc = 2*101.6/1000;  %[m] Diam Ca√±eria
    A_a = pi*(Da^2 - da^2)/4;   %√?rea abrir
    A_c = pi*(Dc^2 - dc^2)/4;   %√?rea cerrar

    Fza_Hid = (u(:,7)*A_c - u(:,6)*A_a)*100/5;
    %Pos_Alabes = u(:, 3);

    %vector tiempo
    t=0:1/10:(length(Fza_Hid)/10)-(1/10);
    t = t';

    %conteo de ciclos rainflow

    [c, rm, rmr, rmm, idx] = rainflow(Fza_Hid);

    t_t = t(idx);
    Fza_Hid_t = Fza_Hid(idx);

    dP = u(:, 7)-u(:, 6); %delta presi√≥n
    lim_inf_max = -0.45*ones(length(t),1);  %l√≠mites para conteo
    lim_inf_min = -0.5*ones(length(t),1);   %l√≠mites para conteo
    lim_sup_max = 0.5*ones(length(t),1);  %l√≠mites para conteo
    lim_sup_min = 0.45*ones(length(t),1);   %l√≠mites para conteo

    Mov_rel = u(:, 8) - u(1, 8);
    %%
    %Gr√°fico de posici√≥n de alabes
    Pos_Alabes = u(:, 3)*((37-10)/100);
    Cons_Alabes = u(:, 11)*((37-10)/100);
    figure;
    plot(t, Pos_Alabes, t, Cons_Alabes);
    legend('Posici√≥n', 'consigna')
    ylabel('grados');
    xlabel('tiempo(s)');
    title('Posici√≥n Alabes');

    %%
    %Gr√°fico de potencia y posici√≥n de alabe
    figure;
    yyaxis left;
    plot(t, u(:, 1));
    ylabel('MW');
    yyaxis right;
    plot(t, Pos_Alabes);
    ylabel('grados');
    xlabel('tiempo(s)');
    title('Potencia y Posici√≥n Alabes');
    legend('Potencia', 'Posici√≥n Alabes');

    %%
    %Gr√°fico potencia y dp

    figure;
    yyaxis left;
    plot(t, u(:, 1));
    ylabel('MW');
    yyaxis right;
    plot(t, dP, t, lim_sup_max, '--r', t, lim_sup_min, '--y', t, lim_inf_min, '--r', t, lim_inf_max, '--y');
    ylabel('bar');
    xlabel('tiempo(s)');
    title('Potencia y Delta presi√≥n');
    legend('Potencia', 'Posici√≥n Alabes', 'L√≠mite m√°ximo superior', 'L√≠mite m√≠nimo superior', 'L√≠mite m√≠nimo inferior', 'L√≠mite m√°ximo inferior');

    %%
    %Gr√°fico dP y movimientos relativos
    % figure;
    % yyaxis right;
    % plot(t, Mov_rel);
    % ylabel('N¬∫');
    % yyaxis left;
    % plot(t, dP, t, lim_sup_max, '--r', t, lim_sup_min, '--y', t, lim_inf_min, '--r', t, lim_inf_max, '--y');
    % ylabel('bar');
    % xlabel('tiempo(s)');
    % title('Potencia y Delta presi√≥n');
    % legend('Delta Presi√≥n', 'L√≠mite m√°ximo superior', 'L√≠mite m√≠nimo superior', 'L√≠mite m√≠nimo inferior', 'L√≠mite m√°ximo inferior', 'Cantidad de Movimientos');

    %%
    %Gr√°fico Fuerza y posici√≥n
    figure;
    yyaxis right;
    plot(t, Pos_Alabes);
    ylabel('grados');
    yyaxis left;
    plot(t, Fza_Hid, t, lim_sup_max, '--r', t, lim_sup_min, '--y', t, lim_inf_min, '--r', t, lim_inf_max, '--y');
    ylabel('kN');
    xlabel('tiempo(s)');
    title('Fuerza y posici√≥n de alabes');
    legend('Fuerza', 'L√≠mite m√°ximo superior', 'L√≠mite m√≠nimo superior', 'L√≠mite m√≠nimo inferior', 'L√≠mite m√°ximo inferior', 'Posici√≥n');


    %%
    %Gr√°fico Fuerza y movimiento
    figure;
    yyaxis right;
    plot(t, Mov_rel);
    ylabel('N¬∫');
    yyaxis left;
    plot(t, Fza_Hid, t, lim_sup_max, '--r', t, lim_sup_min, '--y', t, lim_inf_min, '--r', t, lim_inf_max, '--y');
    ylabel('kN');
    xlabel('tiempo(s)');
    title('Potencia y Delta presi√≥n');
    legend('Delta Presi√≥n', 'L√≠mite m√°ximo superior', 'L√≠mite m√≠nimo superior', 'L√≠mite m√≠nimo inferior', 'L√≠mite m√°ximo inferior', 'Cantidad de Movimientos');


    %%
    figure;plot(t, Fza_Hid, t_t, Fza_Hid_t, 'o')
    title('Fueza en Biela y pico')
    ylabel('kN')
    xlabel('tiempo [s]')

    %%
    [c, rm, rmr, rmm, idx] = rainflow(Fza_Hid);

    rmr1 = rmr(rmr>=50);
    rm1=rm((length(rmr)-length(rmr1)+1):end, :);
    rmr = rmr1;
    rm = rm1;

    % figure; histogram('BinEdges', rmr', 'BinCounts', sum(rm, 2))
    % title('Ciclos vs Rango')
    % xlabel('Rango Fuerza [kN]') 
    % % xlim([rmr(1) rmr(end)])
    % xticks([rmr(1):150:rmr(end) ])
    % ylabel('Ciclos')

    figure; 
    yyaxis left
    plot(t, Fza_Hid);
    yyaxis right
    plot(t, u(:, 3));

    [cFs, rmFs, rmrFs, rmmFs, idxFs] = rainflow(Fza_Hid, Fs);
    To = array2table(cFs,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]'});


    %% 
    % Gr√°ficos dP y Cant. Movimientos
    figure;
    yyaxis left
    plot(t, dP); hold on;
    plot(t, lim_inf_max,'--r', t, lim_inf_min,'--y');
    ylabel('bar');
    ylim([-0.6 0])
    yyaxis right
    plot(t, u(:, 8));
    ylabel('N¬∫');
    xlim([26600 32000]);

    %%
    %CONTEO DE CICLOS CON FILTRO DE AVANCE DE FISURA.
    %DK = 14

    %Obtenici√≥n de curva 
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
    dK_1 = 14;      %umbral para consideraci√≥n de ciclos.
    dK_2 = 10.5;    %umbral para consideraci√≥n de ciclos.
    dK_3 = 7;       %umbral para consideraci√≥n de ciclos.

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
        % path = 'Z:\LABSE\PR178 - Instrumentaci√≥n cubo U05\Mediciones\Datos CHY\U05 - Medici√≥n Semanal Variables\Resultados Rainflow Diarios';
        % path = '\\Posadas-pc\labse\PR178 - Instrumentaci√≥n cubo U05\Mediciones\Datos CHY\U05 - Medici√≥n Semanal Variables\Resultados Rainflow Diarios';
        % path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\conteo rainflow';
    % %     path = '\\schuster-pc\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Resultados Rainflow Diarios\despuÈs';
        path = 'C:\DATOS\Nextcloud\Proyectos LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Resultados Rainflow Diarios';
        path = 'C:\Users\Usuario\Downloads\2025.09.15 - Pruebas';
        
        %LOCAL
        %path = 'C:\DATOS\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Resultados Rainflow Diarios';

        %-------------------USAR DESDE AFUERA DE SCHUSTER-PC-------------------%
    %     file = fullfile('\\schuster-pc\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Resultados Rainflow Diarios' , filename); %Leer archivo en SCHUSTER-PC

        %-------------USAR EN SCHUSTER-PC-------------%
    %     path = 'D:\Nextcloud\LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Resultados Rainflow Diarios';

        file = fullfile(path , filename);
        writetable(To, file, 'Sheet', 'Conteo Rainflow', 'Range', 'A1');


        %escritura tabla valores de dK >= 14
        T = array2table(cFs_filter_dK1,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'});
        % filename = sprintf([name '.xlsx']);
        % path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia (TDMS)\Conteo Rainflow';
        % file = fullfile(path , filename);
        writetable(T, file, 'Sheet', 'delta K = 14', 'Range', 'A1');

        %escritura tabla valores de dK >= 10.5
        T = array2table(cFs_filter_dK2,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'});
        % filename = sprintf([name '.xlsx']);
        % path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia (TDMS)\Conteo Rainflow';
        % file = fullfile(path , filename);
        writetable(T, file, 'Sheet', 'delta K = 10.5', 'Range', 'A1');

        %escritura tabla valores de dK >= 7
        T = array2table(cFs_filter_dK3,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'})
        % filename = sprintf([name '.xlsx']);
        % path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia (TDMS)\Conteo Rainflow';
        % file = fullfile(path , filename);
        writetable(T, file, 'Sheet', 'delta K = 7', 'Range', 'A1');
    end
    %{
    %CONTEO DE CICLOS CON FILTRO DE AVANCE DE FISURA.
    %DK = 10.5
    DK = 10.5
    cFs_filter = [];
    j = 1;
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
        dK = k_s  - k_i;
        if dK >= DK
            cFs_filter(j,:) = [cFs(i, :) dK];
            j = j + 1;
        end
    end

    %C√≥digo viejo.
    %j = 1;
    %for i = 1 : m
    %    k_temp = spline(F, K, [cFs(i, 3) - cFs(i, 2)/2 cFs(i, 3) + cFs(i, 2)/2]);
    %    dK = k_temp(2) - k_temp(1);
    %    if dK >= DK
    %        cFs_filter(j,:) = [cFs(i, :) dK];
    %        j = j + 1;
    %    end
    %end



    %escritura tabla valores de dK >= 10.5
    T = array2table(cFs_filter,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'});
    filename = sprintf([name '.xlsx']);
    path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia (TDMS)\Conteo Rainflow';
    file = fullfile(path , filename);
    writetable(T, file, 'Sheet', 'delta K = 10.5', 'Range', 'A1');

    %CONTEO DE CICLOS CON FILTRO DE AVANCE DE FISURA.
    %DK = 7
    DK = 7
    cFs_filter = [];
    j = 1;
    for i = 1 : m
        k_temp = spline(F, K, [cFs(i, 3) - cFs(i, 2)/2 cFs(i, 3) + cFs(i, 2)/2]);
        dK = k_temp(2) - k_temp(1);
        if dK >= DK
            cFs_filter(j,:) = [cFs(i, :) dK];
            j = j + 1;
        end
    end
    % %escritura tabla valores de dK >= 7
    % T = array2table(cFs_filter,'VariableNames',{'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]', 'delta K'})
    % filename = sprintf([name '.xlsx']);
    % path = 'C:\DATOS\LABSE\CHY\U05\Mediciones\CHY\Modo Potencia sin Influencia (TDMS)\Conteo Rainflow';
    % file = fullfile(path , filename);
    % writetable(T, file, 'Sheet', 'delta K = 7', 'Range', 'A1');
    % 
    %}
    close all
    % figure; plot(t, u(:, 1));
    % figure;
    % plot(t, Pos_Alabes, t, Cons_Alabes);
    % legend('PosiciÛn', 'consigna')
    % ylabel('grados');
    % xlabel('tiempo(s)');
    % title('PosiciÛn Alabes');
    X = [name, ' - Cantidad de Movimientos: ', num2str(Mov_rel(end))];
    disp(X) 
    % disp("FINALIZADO")
%     figure; plot(u(:,13)); ylim([0 110]);
%{    
%%
    %{
    ESTA SECCI”N CUENTA EL N⁄MERO DE ARRANQUE Y PARADAS DE LA UNIDAD Y LAS
    ACUMULA EN LA VARIABLE "conteoArranqueParada".
    %}
    conteoArranque = 0;
    conteoParada = 0;
    estadoVelocidad = double(u(:, 13) > 50);
    anterior = estadoVelocidad(1);
    % Separar en fecha y sufijo
    partes = split(name, '-');
    fecha = split(partes{1}, '.');

    % Formatear con ceros
    name = sprintf('%02d.%02d.%02d-%s', str2double(fecha{1}), str2double(fecha{2}), str2double(fecha{3}), partes{2});

    %     disp(nuevoName);  % Resultado: '25.03.10-u05'
    if primerPasada
        conteoArranqueParada = 331 %VALOR DE ARRANQUE Y PARADA AL 28/2/2025
    else
        historico = load(['C:\DATOS\Nextcloud\Proyectos LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Arranques y Paradas\' name(4:5) ' ArranqueyParadas.mat']);
        conteoArranqueParada = historico.conteoArranqueParada(end);
    end

    for ii = estadoVelocidad'
        if ii ~= anterior
            conteoArranqueParada = conteoArranqueParada + 1;
            if anterior > ii
               conteoParada = conteoParada + 1;
            else
                conteoArranque = conteoArranque + 1;
            end
            anterior = ii;
        end
    end
    X = [name, ' - Arranques: ', num2str(conteoArranque)];
    disp(X) 
    X = [name, ' - Paradas: ', num2str(conteoParada)];
    disp(X)
    X = [name, ' - Arranques/Paradas Acumuladas: ', num2str(conteoArranqueParada)];
    disp(X)

%     mismoArchivo = false;
%     if ~primerPasada
%         if ~strcmp(name, historico.name(end, :))
%             conteoArranque = [historico.conteoArranque conteoArranque];
%             conteoParada  = [historico.conteoParada conteoParada];
%             conteoArranqueParada = [historico.conteoArranqueParada conteoArranqueParada];
%             name = [historico.name; name];
%         else
%             disp('Ya se proceso ese archivo, no se va a guardar los arranque y paradas');
%             mismoArchivo = true;
%         end
%     % else
%     %     disp('Ya se proceso ese archivo, no se va a guardar los arranque y paradas');
%     end
%     if ~mismoArchivo
%         save(fullfile('C:\DATOS\Nextcloud\Proyectos LABSE\PR178 - InstrumentaciÛn cubo U05\Mediciones\Datos CHY\U05 - MediciÛn Semanal Variables\Arranques y Paradas',...
%         [name(end, 4:5) ' ArranqueyParadas']),'name', 'conteoArranque',...
%         'conteoParada', 'conteoArranqueParada');
%     end
%}
end
disp("FINALIZADO")