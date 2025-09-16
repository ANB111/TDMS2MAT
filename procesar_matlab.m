function procesar_matlab(matFilePath, excelFolder, graficos, escritura, fs, n_channels)
% procesar_matlab  Procesa un .MAT y produce tablas Excel y (opcionalmente) gráficos.
%
%   procesar_matlab(matFilePath, excelFolder, graficos, escritura, fs, n_channels)
%
%   - matFilePath: ruta completa al archivo .mat que contiene la variable `data`.
%   - excelFolder: carpeta donde se guardarán los .xlsx.
%   - graficos:    true para generar gráficos.
%   - escritura:   true para escribir tablas Excel.
%   - fs:          frecuencia de muestreo en Hz.
%   - n_channels:  número de canales (actualmente no usado, pero disponible).

    %— Validaciones iniciales
    assert(isfile(matFilePath), "No existe el .MAT: %s", matFilePath);
    if escritura && ~isfolder(excelFolder)
        mkdir(excelFolder);
    end

    %— Carga del archivo
    S = load(matFilePath);
    assert(isfield(S,'data'), "El .MAT debe contener la variable 'data'");
    u = S.data;

    %— Extraer nombre base (sin extensión)
    [~, name] = fileparts(matFilePath);

    %— Parámetros geométricos
    Da = 2*762/1000; da = 2*350/1000;
    Dc = Da;        dc = 2*101.6/1000;
    A_a = pi*(Da^2 - da^2)/4;
    A_c = pi*(Dc^2 - dc^2)/4;

    %— Señal hidráulica y vector tiempo
    Fza_Hid = (u(:,7)*A_c - u(:,6)*A_a)*(100/5);
    N = size(Fza_Hid,1);
    t = (0:N-1)'/fs;

    %— Conteo rainflow básico
    [c, ~, rmr, ~, idx] = rainflow(Fza_Hid);
    t_peaks   = t(idx);
    Fza_peaks = Fza_Hid(idx);

    %— Delta presión y límites
    dP = u(:,7) - u(:,6);
    lim_sup =  0.45;
    lim_inf = -0.45;

    %— Rainflow con muestreo fs
    [cFs, ~, ~, ~, ~] = rainflow(Fza_Hid, fs);
    To = array2table(cFs, ...
        'VariableNames', {'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]'});


    %— Filtrado ΔK en 3 umbrales
    K = [65.12307378 57.01521195 42.83250569 27.55061352 14.93805445 7.055368592 3.505949635 2.470266626 2.331041354]';
    F = [1782 1560 1337 1114 891 668 446 223 100]';
    pp = spline(F, K);

    dK_thr = [14, 10.5, 7];

    % Preparo variables
    nCols = size(cFs,2);
    if nCols == 0
        nCols = 5; % seguridad (esperamos 5 columnas en cFs: Ciclos,Rango,Media,ti,ts)
    end

    % Si cFs está vacío, genero filas vacías para cada filtro
    filtros = cell(1,3);
    if isempty(cFs)
        for k = 1:3
            filtros{k} = zeros(1, nCols + 1); % fila de ceros con columna extra delta K
        end
    else
        % Vectorizo cálculo de f_i y f_s
        medias = cFs(:,3);
        rangos = cFs(:,2);
        f_i = medias - rangos/2;   % fuerza mínima
        f_s = medias + rangos/2;   % fuerza máxima

        % Evaluar K en f_i y f_s, cuidando f < 0
        k_i = zeros(size(f_i));
        k_s = zeros(size(f_s));

        pos_i = f_i > 0;
        if any(pos_i)
            % Usamos ppval (igual que tu script original). Alternativa: interp1(...,'pchip','extrap')
            k_i(pos_i) = ppval(pp, f_i(pos_i));
        end
        pos_s = f_s > 0;
        if any(pos_s)
            k_s(pos_s) = ppval(pp, f_s(pos_s));
        end

        dK_vals = k_s - k_i; % ΔK para cada ciclo

        % Construyo las tablas filtradas (añadiendo la columna delta K)
        for k = 1:3
            idx_sel = dK_vals >= dK_thr(k);
            sel = [cFs(idx_sel, :) dK_vals(idx_sel)];
            if isempty(sel)
                sel = zeros(1, nCols + 1);
            end
            filtros{k} = sel;
        end
    end

    %— Escritura Excel
    if escritura
        outFile = fullfile(excelFolder, name + ".xlsx");
        writetable(To, outFile, 'Sheet','Conteo Rainflow','Range','A1');
        for k = 1:3
            sheet = sprintf("delta K = %g", dK_thr(k));
            T = array2table(filtros{k}, ...
                'VariableNames', {'Ciclos','Rango [kN]','Media [kN]','ti [s]','ts [s]','delta K'});
            writetable(T, outFile, 'Sheet',sheet,'Range','A1');
        end
    end

    %— Gráficos opcionales
    if graficos
        % 1. Posición de álabes
        Pos = u(:,3)*((37-10)/100);
        figure; plot(t,Pos,'LineWidth',1.2);
        xlabel('Tiempo (s)'); ylabel('Álabes (°)');
        title('Posición de Álabes');

        % 2. Potencia vs posición
        figure;
        yyaxis left;  plot(t,u(:,1)); ylabel('MW');
        yyaxis right; plot(t,Pos);    ylabel('°');
        title('Potencia y Posición de Álabes');

        % 3. Potencia y ΔP
        figure; hold on;
        yyaxis left;  plot(t,u(:,1)); ylabel('MW');
        yyaxis right;
        plot(t,dP,'-', t,lim_sup*ones(N,1),'--r', t,lim_inf*ones(N,1),'--b');
        ylabel('ΔP (bar)');
        title('Potencia y Delta Presión');
        legend('Potencia','ΔP','Lím Sup','Lím Inf');

        % 4. Picos rainflow
        figure; plot(t_peaks,Fza_peaks,'o');
        xlabel('Tiempo (s)'); ylabel('Pico Fza (kN)');
        title('Picos Rainflow');

        % 5. Curva K
        K = [65.1231 57.0152 42.8325 27.5506 14.9381 7.0554 3.5059 2.4703 2.3310]';
        F = [1782 1560 1337 1114 891 668 446 223 100]';
        pp = spline(F,K);
        ff = linspace(min(F),max(F),200);
        figure; plot(ff,ppval(pp,ff),F,K,'*r');
        xlabel('Fuerza (kN)'); ylabel('Factor K (MPa·m^{1/2})');
        title('Curva Factor K');
    end

    %— Mensaje final
    fprintf("%s → FINALIZADO\n", name);
end
