import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit, root_scalar
from StarData import cyc116, ND4, PointSpread
from datetime import datetime
from scipy.ndimage import gaussian_filter1d
import StarGUI
import DiskGUI


StarGUI.start(cyc116)

# DiskGUI.start(cyc116)


def scaling_func(pos, a, b):
    return a * (pos - b)


def scaling_gauss_func(pos, a, b, sig):
    return a * (gaussian_filter1d(pos, sig) - b)


def mkdir_p(mypath):
    '''Creates a directory. equivalent to using mkdir -p on the command line'''

    from errno import EEXIST
    from os import makedirs, path

    try:
        makedirs(mypath)
    except OSError as exc:
        if exc.errno == EEXIST and path.isdir(mypath):
            pass
        else:
            raise


def align_yaxis(ax1, v1, ax2, v2):
    """adjust ax2 ylimit so that v2 in ax2 is aligned to v1 in ax1"""
    _, y1 = ax1.transData.transform((0, v1))
    _, y2 = ax2.transData.transform((0, v2))
    adjust_yaxis(ax2, (y1 - y2) / 2, v2)
    adjust_yaxis(ax1, (y2 - y1) / 2, v1)


def adjust_yaxis(ax, ydif, v):
    """shift axis ax by ydiff, maintaining point v at the same location"""
    inv = ax.transData.inverted()
    _, dy = inv.transform((0, 0)) - inv.transform((0, ydif))
    miny, maxy = ax.get_ylim()
    miny, maxy = miny - v, maxy - v
    if -miny > maxy or (-miny == maxy and dy > 0):
        nminy = miny
        nmaxy = miny * (maxy + dy) / (miny + dy)
    else:
        nmaxy = maxy
        nminy = maxy * (miny + dy) / (maxy + dy)
    ax.set_ylim(nminy + v, nmaxy + v)


plt.figure(figsize=(8, 8))
plt.imshow(cyc116.radial[0, 0], vmin=-50, vmax=110, cmap='gray')
plt.ylim((400, 624))
plt.xlim((400, 624))
plt.yticks(np.linspace(0, 1, 5) * 224 + 400, fontsize=18)
plt.xticks(np.linspace(0, 1, 5) * 224 + 400, fontsize=18)

plt.figure(figsize=(8, 8))
plt.imshow(np.log10(1e-2 * cyc116.get_i_img()[0] + 1), cmap='gray')
plt.yticks(fontsize=18)
plt.xticks(fontsize=18)

plt.show()

first = 14
second = 65
peak = 32
y_min = 0.1
tail = np.linspace(120, 200, 8, dtype=int, endpoint=False)

nd4_region = np.concatenate((np.arange(first, second), tail))
psf_region = np.concatenate((np.arange(first, peak), tail))

markers_on_nd4 = [first, second, *tail]
markers_on_psf = [peak, *tail]
weights_nd4 = np.concatenate((np.full((21 - first,), 2), np.full((second - 21,), 1), np.full_like(tail, 1000)))
weights_psf = np.concatenate((np.full((peak - first,), 3.5), np.full_like(tail, 1)))
bounds_psf = ([0, -np.inf, 0], np.inf)
save = False
smart = False
mixed = True
results = []
results_err = []

profile = ["I-band", "R-band"]

if save:
    folder = datetime.now().strftime('%d_%m_%H%M')
    path = "../Bilder/" + folder
    mkdir_p(path)

    param_file = open(path + "/parameters.txt", "w")

for index in [0, 1]:
    print(profile[index])
    # cyc116_img = cyc116.get_i_img()[0]
    x, cyc116_profile, cyc116_err = cyc116.azimuthal[index]
    _, nd4_profile, nd4_err = ND4.azimuthal[index]

    _, psf, psf_err = PointSpread.azimuthal[index]

    x2, qphi, qphi_err = cyc116.azimuthal_qphi[index]

    guess = (1.0 / ND4.filter_reduction[index], np.median(nd4_profile[100:]))
    print("guess: ", guess)

    scaling_factor = curve_fit(scaling_func, nd4_profile[nd4_region], cyc116_profile[nd4_region], p0=guess,
                               sigma=weights_nd4)
    print("scaling factor", scaling_factor)

    scaled_profile = scaling_func(nd4_profile, *scaling_factor[0])

    scaled_profile_err = scaling_factor[0][0] ** 2 * scaling_factor[1][1, 1]
    scaled_profile_err += (nd4_profile - scaling_factor[0][1]) ** 2 * scaling_factor[1][0, 0]
    scaled_profile_err = np.sqrt(scaled_profile_err)

    mixed_profile = cyc116_profile.copy()
    mixed_profile[:80] = scaled_profile[:80]
    if mixed:
        scaled_profile = mixed_profile
        name = "mixed ND4 profile"
    else:
        name = "scaled profile of ND4"

    if smart:
        tail = np.array((np.abs(scaled_profile[120:200] - cyc116_profile[120:200]) / cyc116_profile[
                                                                                     120:200] <= 0.6827 / 2).nonzero()) \
               + 120
        print("Points satisfy condition: ", len(tail[0]))
        tail = tail[0, ::-len(tail[0]) // 8]
        tail = tail[::-1]
        psf_region = np.concatenate((np.arange(peak), tail))
        weights_psf = np.concatenate((np.full((peak,), 4.50), np.full_like(tail, 1)))
        markers_on_psf = [peak, *tail]

    psf_factor = curve_fit(scaling_gauss_func, psf[psf_region], scaled_profile[psf_region],
                           sigma=weights_psf, bounds=bounds_psf)
    print("psf factor", psf_factor)

    psf_profile = scaling_gauss_func(psf, *psf_factor[0])

    psf_profile_err = psf_factor[0][0] ** 2 * psf_factor[1][1, 1]
    psf_profile_err += (nd4_profile - psf_factor[0][1]) ** 2 * psf_factor[1][0, 0]
    psf_profile_err = np.sqrt(psf_profile_err)

    disk_profile = cyc116_profile - psf_profile
    disk_profile_err = psf_profile_err ** 2
    disk_profile_err += cyc116_err ** 2
    disk_profile_err = np.sqrt(disk_profile_err)

    fig_comp = plt.figure(figsize=(14, 7))
    textax = plt.axes([0.5, 0.95, 0.3, 0.03], figure=fig_comp)
    textax.axis('off')
    textax.text(0, 0, "Comparison " + profile[index] + " of ND4 to cyc116", fontsize=18, ha='center')

    ax = fig_comp.add_subplot(1, 1, 1)
    ax.plot(x, cyc116_profile, '-D', label="profile of cyc116", markevery=markers_on_nd4)
    #  ax.fill_between(x, cyc116_profile + cyc116_err, cyc116_profile - cyc116_err, alpha=0.5, color='C0')
    ax.plot(x, scaled_profile, '-D', label=name, markevery=list(tail))
    nd4_equation = R"$({:.2e})\cdot(ND4-({:.2e}))$".format(*scaling_factor[0])
    ax.plot([], [], ' ', label=nd4_equation)
    ax.plot(x, psf_profile, '-DC2', label="PSF profile", markevery=markers_on_psf)
    psf_equation = R"$({:.2e})\cdot(gauss(PSF,{:.2e})-({:.2e}))$".format(*psf_factor[0])
    ax.plot([], [], ' ', label=psf_equation)
    ax.fill_between(range(22), psf_profile[:22] * 0.178, psf_profile[:22] * 3.16, alpha=0.5, color="gold")
    ax.legend(fontsize='large', framealpha=1)
    ax.set_yscale('log', nonposy='clip')
    ax.set_ylim(ymin=y_min)

    zoom_xax = (5, 63)

    axins = ax.inset_axes([0.35, 0.55, 0.5, 0.43])
    axins.semilogy(x, cyc116_profile, '-D', label="profile of cyc116", markevery=markers_on_nd4)
    axins.semilogy(x, scaled_profile, '-D', label=name, markevery=list(tail))
    axins.semilogy(x, psf_profile, '-D', label="PSF profile", markevery=markers_on_psf)
    axins.set_ylim(
        (0.9 * np.min(psf_profile[zoom_xax[0]:zoom_xax[1]]), 1.05 * np.max(psf_profile[zoom_xax[0]:zoom_xax[1]])))
    axins.set_xlim(zoom_xax)
    ax.indicate_inset_zoom(axins)

    fig_sub = plt.figure(figsize=(16, 7))
    textax = plt.axes([0.5, 0.95, 0.3, 0.03], figure=fig_sub)
    textax.axis('off')
    textax.text(0, 0, "Subtraction in " + profile[index], fontsize=18, ha='center')

    ax = fig_sub.add_subplot(1, 1, 1)
    line1, = ax.plot(x, disk_profile, label="Reduced cyc116 profile")
    ax1 = ax.twinx()
    line2, = ax1.plot(x2[20:], qphi[20:], "C3", label="Qphi profile")
    ax.tick_params(axis='y', labelcolor="C0")
    ax1.tick_params(axis='y', labelcolor="C3")
    ax1.set_ylim(ymin=-10, ymax=1.1 * max(qphi[20:]))
    ax.set_ylim(ymin=-100, ymax=1.1 * max(disk_profile[20:]))
    line3 = ax.axhline(0, ls='--', c='k', alpha=0.5, label="zero")
    lines = [line1, line2, line3]
    align_yaxis(ax, 0, ax1, 0)
    ax.fill_between([32, 118], [-110, -110], [1000, 1000], alpha=0.2, color="gold")
    ax.legend(lines, [line.get_label() for line in lines], fontsize='large', framealpha=1)

    if save:
        fig_comp.savefig(path + "/Comparison_" + profile[index] + ".png", dpi=150)
        fig_sub.savefig(path + "/Subtraction_" + profile[index] + ".png", dpi=150)

        param_file.write("\n" + profile[index] + "\n")
        param_file.write("Mixed: {}\n".format(mixed))
        param_file.write("Smart: {}\n".format(smart))
        param_file.write("ND4:\n")
        param_file.write("Region: {}\n".format(nd4_region))
        param_file.write("Weights: {}\n".format(weights_nd4))

        param_file.write("PSF:\n")
        param_file.write("Region: {}\n".format(psf_region))
        param_file.write("Weights: {}\n".format(weights_psf))
        param_file.write("\nScaling factor: {}\n".format(scaling_factor[0]))
        param_file.write(("PSF factor: {}\n".format(psf_factor[0])))

    disk_profile[disk_profile < 0] = 0
    results.append([np.sum(disk_profile[32:118]) - np.median(disk_profile[130:]) * (118 - 32), np.sum(qphi[24:118]),
                    np.sum(psf_profile[:22]) - np.median(cyc116_profile[130:]) * 22])
    results_err.append(
        [np.sum(disk_profile_err[32:118] ** 2) - np.std(disk_profile[130:]) ** 2 * (118 - 32),
         np.sum(qphi_err[24:118] ** 2),
         np.sum(psf_profile_err[:22] ** 2) - np.std(cyc116_profile[130:]) ** 2 * 22])
    print("Counts fit: ", np.sum(disk_profile[32:118]) - np.median(disk_profile[130:]) * (118 - 32))
    print("Qphi counts: ", np.sum(qphi[24:118]))
    print("PSF counts: ", np.sum(psf_profile[:22]) - np.median(cyc116_profile[130:]) * 22)
    print("errors: ", results_err)

if save:
    print("File saved")
    param_file.close()

""" 2d attempt """

# first = 11
# second = 38
# y_min = 0.1
# markers_on = [first, second]
# profile = ["I-band", "R-band"]
# a = 1000
#
# for index in [0]:
#     print(profile[index])
#     map1 = cyc116.get_i_img()[index]
#     map2 = ND4.get_i_img()[index]
#     _, radial2 = ND4.azimuthal[index]
#     psf = PointSpread.get_i_img()[index]
#
#     qphi = cyc116.radial[index, 0]
#
#     region = annulus(map1[0].size, second, first)
#     outer_region = annulus(map1[0].size, np.inf, 200)
#     disk = annulus(map1[0].size, 125, 32)
#
#     guess = (1.0 / ND4.filter_reduction[index], np.median(radial2[100:]))
#     print("guess: ", guess)
#     max_cor = np.argmax(map2[region])
#     print("maximum location", max_cor)
#     print(map2[region].flatten()[max_cor])
#     psf_factor = guess[0] * (map2[region].flatten()[max_cor] - guess[1]) / psf[region].flatten()[max_cor]
#     print("psf factor:", psf_factor)

# plt.figure()
# plt.semilogy(range(0, 1024), map1[512, :])
# plt.semilogy(range(0, 1024), guess[0] * (map2[512, :] - guess[1]))  # links rechts
# plt.semilogy(range(0, 1024), psf_factor * psf[512, :])
#
# plt.figure()
# plt.semilogy(range(0, 1024), map1[:, 512])
# plt.semilogy(range(0, 1024), guess[0] * (map2[:, 512] - guess[1]))  # oben unten
# plt.semilogy(range(0, 1024), psf_factor * psf[:, 512])
#
# plt.figure()
# plt.semilogy(range(0, 1024), map1[512, :] - psf_factor * psf[512, :])
#
# plt.figure()
# plt.semilogy(range(0, 1024), map1[:, 512] - psf_factor * psf[:, 512])

# disk_map = map1 - psf_factor * psf
# disk_map[disk_map < 0] = 0
# print("Counts manual: ", np.sum(disk_map[disk]))

# for obj in gc.get_objects():
#     if isinstance(obj, StarImg):
#         print(obj.name)
#         x, radial = azimuthal_averaged_profile(obj.get_i_img()[0])
#         # x, radial = half_azimuthal_averaged_profile(obj.get_i_img()[0])
#         fig = plt.figure(num=obj.name)
#         ax1 = fig.add_subplot(131)
#         ax1.set_title("azimuthal rofile")
#         ax1.semilogy(x, radial)
#         ax2 = fig.add_subplot(132)
#         ax2.set_title("first derivative")
#         ax2.plot(x, np.gradient(radial))
#         ax3 = fig.add_subplot(133)
#         ax3.set_title("second derivative")
#         sec = np.gradient(np.gradient(radial))
#         sec_deriv_func = interpolate.interp1d(x, sec)
#
#
#         def sec_deriv_sq(x):
#             return sec_deriv_func(x) ** 2
#
#
#         thin = np.linspace(x[0], x[-1], 10000)
#         ax3.plot(thin, sec_deriv_sq(thin))
#         results = diffraction_rings(radial, 19, width=10)
#         print(np.array2string(results[0], precision=2))
#         print(np.array2string(results[1], precision=2))
#
#         textax = plt.axes([0.5, 0.95, 0.3, 0.03])
#         textax.axis('off')
#         textax.text(0, 0, obj.name, fontsize=18, ha='center')

print("Results:")
results = np.array(results)
results_err = np.sqrt(np.abs(results_err))
print("I/R: ", results[0] / results[1])
error = (results_err[0] / results[1]) ** 2
error += (results_err[1] * results[0] / results[1] ** 2) ** 2
error = np.sqrt(error)
print("Errors: ", error)
plt.show()
